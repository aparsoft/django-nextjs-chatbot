# /home/ram/aparsoft/backend/apps/accounts/api/views/profile_avatar_views.py

# accounts/api/views/profile_avatar_views.py

"""
Profile Avatar Views

Handles avatar upload, update, and removal with image optimization.
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from drf_spectacular.utils import extend_schema, extend_schema_view
from PIL import Image
import os
import uuid
import logging
from io import BytesIO

from ...utils.profile_picture_utils import (
    has_profile_picture_field,
    get_profile_picture_url,
    set_profile_picture,
    delete_profile_picture,
)
from ..serializers.response_serializers import (
    AvatarResponseSerializer,
    AvatarDeleteResponseSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()


@extend_schema_view(
    get=extend_schema(
        tags=["Profile"],
        summary="Get avatar",
        description="Retrieve the authenticated user's profile image URL.",
        responses={200: AvatarResponseSerializer},
    ),
    post=extend_schema(
        tags=["Profile"],
        summary="Upload avatar",
        description="Upload or update the authenticated user's profile avatar. Accepts JPEG, PNG, WebP up to 5 MB.",
        request={"multipart/form": {"type": "object", "properties": {"profile_picture": {"type": "string", "format": "binary"}}}},
        responses={200: AvatarResponseSerializer, 400: AvatarResponseSerializer},
    ),
    delete=extend_schema(
        tags=["Profile"],
        summary="Delete avatar",
        description="Remove the authenticated user's profile avatar.",
        responses={200: AvatarDeleteResponseSerializer},
    ),
)
class ProfileAvatarView(APIView):
    """Handle avatar upload, update, and removal for user profiles."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get current user's profile image URL."""
        try:
            user = request.user
            
            # Use utility function to safely get profile picture URL
            profile_picture_url = get_profile_picture_url(user, request)
            
            if profile_picture_url:
                return Response({
                    'message': 'Profile image found',
                    'status': 'success',
                    'data': {
                        'profile_picture_url': profile_picture_url
                    }
                }, status=status.HTTP_200_OK)
            else:
                # Check if the field exists to provide appropriate message
                if not has_profile_picture_field(user):
                    return Response({
                        'message': 'Profile picture feature not available. Please run database migrations.',
                        'status': 'error',
                        'data': {
                            'profile_picture_url': None
                        },
                        'error_code': 'FIELD_NOT_FOUND'
                    }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                else:
                    return Response({
                        'message': 'No profile image found',
                        'status': 'info',
                        'data': {
                            'profile_picture_url': None
                        }
                    }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Profile image retrieval error for user {request.user.id}: {str(e)}", exc_info=True)
            return Response({
                'message': 'Failed to retrieve profile image',
                'status': 'error',
                'data': {
                    'profile_picture_url': None
                },
                'error_code': 'RETRIEVAL_ERROR'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        """Upload/update user avatar."""
        try:
            user = request.user
            
            # Check if profile_picture field exists
            if not has_profile_picture_field(user):
                return Response({
                    'message': 'Profile picture feature not available. Please run database migrations.',
                    'status': 'error',
                    'error_code': 'FIELD_NOT_FOUND'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Check if file was uploaded
            if 'profile_picture' not in request.FILES:
                return Response({
                    'message': 'No image file provided',
                    'status': 'error'
                }, status=status.HTTP_400_BAD_REQUEST)

            image_file = request.FILES['profile_picture']
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
            if image_file.content_type not in allowed_types:
                return Response({
                    'message': 'Invalid file type. Only JPEG, PNG, and WebP are allowed.',
                    'status': 'error'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate file size (5MB max)
            max_size = 5 * 1024 * 1024  # 5MB
            if image_file.size > max_size:
                return Response({
                    'message': 'File size too large. Maximum 5MB allowed.',
                    'status': 'error'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Process and optimize image
            try:
                optimized_image = self.optimize_image(image_file)
            except Exception as e:
                logger.error(f"Image optimization failed for user {user.id}: {str(e)}")
                return Response({
                    'message': 'Failed to process image. Please try a different image.',
                    'status': 'error'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Delete old avatar if exists (handled in set_profile_picture utility)

            # Generate unique filename
            file_extension = 'jpg'  # Always save as JPEG after optimization
            filename = f"avatars/user_{user.id}_{uuid.uuid4().hex[:8]}.{file_extension}"

            # Save optimized image
            saved_path = default_storage.save(filename, ContentFile(optimized_image.getvalue()))
            
            # Update user model using utility function
            success = set_profile_picture(user, saved_path)
            
            if not success:
                # Clean up the file if setting failed
                try:
                    default_storage.delete(saved_path)
                except Exception:
                    pass
                return Response({
                    'message': 'Failed to save avatar',
                    'status': 'error'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Generate full URL
            avatar_url = request.build_absolute_uri(default_storage.url(saved_path))

            logger.info(f"Avatar updated successfully for user {user.id}")

            return Response({
                'message': 'Avatar updated successfully',
                'status': 'success',
                'data': {
                    'profile_picture_url': avatar_url
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Avatar upload error for user {request.user.id}: {str(e)}", exc_info=True)
            return Response({
                'message': 'Failed to upload avatar',
                'status': 'error',
                'error_code': 'UPLOAD_ERROR'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request):
        """Remove user avatar."""
        try:
            user = request.user
            
            # Check if profile_picture field exists
            if not has_profile_picture_field(user):
                return Response({
                    'message': 'Profile picture feature not available. Please run database migrations.',
                    'status': 'error',
                    'error_code': 'FIELD_NOT_FOUND'
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Use utility function to safely delete profile picture
            success = delete_profile_picture(user)
            
            if success:
                return Response({
                    'message': 'Avatar removed successfully',
                    'status': 'success'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'message': 'Failed to remove avatar',
                    'status': 'error',
                    'error_code': 'DELETION_ERROR'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.error(f"Avatar removal error for user {request.user.id}: {str(e)}", exc_info=True)
            return Response({
                'message': 'Failed to remove avatar',
                'status': 'error',
                'error_code': 'DELETION_ERROR'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def optimize_image(self, image_file, size=(200, 200), quality=85):
        """
        Optimize uploaded image for avatar use.
        
        Args:
            image_file: Uploaded image file
            size: Target size tuple (width, height)
            quality: JPEG quality (1-100)
            
        Returns:
            BytesIO: Optimized image data
        """
        try:
            # Open image with PIL
            with Image.open(image_file) as img:
                # Convert to RGB if necessary (handles PNG with transparency, etc.)
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Calculate dimensions for center crop to square
                width, height = img.size
                if width > height:
                    # Landscape: crop sides
                    left = (width - height) // 2
                    top = 0
                    right = left + height
                    bottom = height
                else:
                    # Portrait: crop top/bottom
                    left = 0
                    top = (height - width) // 2
                    right = width
                    bottom = top + width

                # Crop to square
                img = img.crop((left, top, right, bottom))
                
                # Resize to target size with high-quality resampling
                img = img.resize(size, Image.Resampling.LANCZOS)

                # Save optimized image to BytesIO
                output = BytesIO()
                img.save(output, format='JPEG', quality=quality, optimize=True)
                output.seek(0)
                
                return output

        except Exception as e:
            logger.error(f"Image optimization error: {str(e)}")
            raise

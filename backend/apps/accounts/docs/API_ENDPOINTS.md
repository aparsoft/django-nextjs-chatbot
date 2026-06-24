# Accounts API Endpoints

> Base: `/api/v1/accounts/` · Auth: `Authorization: Bearer <access>` (except auth endpoints)
> All responses use the custom envelope: `{ "message", "status", "data" }` on success.

---

## Authentication

### POST `auth/login/`
**Auth:** None · **Body:** `{ "email", "password" }`
**200:** `{ "message": "Login successful", "status": "success", "data": { "tokens": { "access", "refresh" }, "user": { "id", "email", "first_name", "last_name", "full_name", "role", "status", "email_verified", "profile_completion": { "is_complete", "missing_fields", "next_steps" } }, "navigation": { "dashboard_route", "next_action" }, "session_info": { "login_count", "last_login" } } }`
**401:** `{ "message", "code": "authentication_failed", "status": "error" }`

### POST `auth/refresh/`
**Auth:** None · **Body:** `{ "refresh" }` (or reads `refresh_token` cookie)
**200:** `{ "access", "refresh" }` (new refresh — rotation is on)

### POST `auth/verify/`
**Auth:** None · **Body:** `{ "token" }`
**200:** `{}` (empty)

### POST `auth/logout/`
**Auth:** None · **Body:** `{ "refresh", "all_devices"?: false }`
**200:** `{ "message", "code", "status": "success" }`

### POST `auth/register/`
**Auth:** None · **Body:** `{ "email", "password1", "password2", "first_name", "last_name", "role"?: "user", "username"?: "" }`
**201:** `{ "message", "status": "success", "user": { "id", "email", "username", "first_name", "last_name", "role", "email_verified" }, "tokens": { "access", "refresh" }, "next_steps": [] }`

### POST `auth/social/google/`
**Auth:** None · **Body:** `{ "id_token" }`
**200:** `{ "message": "Login successful", "status": "success", "data": { "tokens": { "access", "refresh" }, "user": { "id", "email", "full_name", "role", "email_verified" }, "created": bool } }`
**401:** `{ "message", "code": "invalid_google_token", "status": "error" }`

### POST `auth/password/reset/`
**Auth:** None · **Body:** `{ "email" }`
**200:** `{ "message": "If an account exists, reset instructions will be sent", "status": "success" }`

### POST `auth/password/reset/confirm/`
**Auth:** None · **Body:** `{ "uid", "token", "new_password", "confirm_password" }`
**200:** `{ "message": "Password reset successful", "status": "success" }`

### GET `auth/password/reset/confirm/?uid=&token=`
**200:** `{ "message": "Token validated", "status": "success", "valid": true, "user_email" }`

### POST `auth/password/change/`
**Auth:** Yes · **Body:** `{ "current_password", "new_password" }`
**200:** `{ "message": "Password changed successfully", "status": "success" }`

### POST `auth/email/verify/`
**Auth:** Yes · **Body:** (empty)
**200:** `{ "message": "Verification email sent", "status": "success" }`

### GET `auth/email/verify/?uid=&token=`
**Auth:** None
**200:** `{ "message": "Email verified successfully", "status": "success" }`

### GET `auth/csrf/`
**Auth:** None
**200:** `{ "message": "CSRF cookie set successfully", "status": "success", "csrfToken" }`

---

## Users

### GET `users/`
**Auth:** Yes · **Query:** `?role=&is_active=&email_verified=&search=&ordering=`
**200:** `[ { "id", "username", "email", "full_name", "role", "is_active", "email_verified" } ]`

### POST `users/`
**Auth:** Yes (admin) · **Body:** `{ "email", "username", "password", "first_name", "last_name", "role" }`
**201:** Full user object (see GET `users/{id}/`)

### GET `users/{id}/`
**Auth:** Yes
**200:** `{ "id", "username", "email", "first_name", "last_name", "full_name", "role", "profile_picture", "email_verified", "phone_verified", "two_factor_enabled", "last_password_change", "last_active", "login_count", "date_joined", "is_active", "contact": { "id", "address_line1", "address_line2", "city", "state", "postal_code", "country", "country_name", "contact_info": {}, "timezone", "availability" } }`

### PATCH `users/{id}/`
**Auth:** Yes · **Body:** (any subset) `{ "username", "email", "first_name", "last_name", "role" }`
**200:** Updated user object

### DELETE `users/{id}/`
**Auth:** Yes (admin or owner) · **204:** No content

### GET `users/me/`
**Auth:** Yes
**200:** Full user object (same shape as `users/{id}/`)

### POST `users/{id}/verify-email/`
**Auth:** Yes (admin) · **Body:** (empty)
**200:** `{ "message": "Email verified successfully", "status": "success" }`

### POST `users/{id}/change-password/`
**Auth:** Yes · **Body:** `{ "current_password", "new_password" }`
**200:** `{ "message": "Password changed successfully", "status": "success" }`

### GET `users/{id}/profile-image/`
**Auth:** Yes
**200:** `{ "message", "status": "success", "data": { "profile_picture_url" } }`

### GET `users/stats/`
**Auth:** Yes (admin)
**200:** `{ "total_users", "active_users", "verified_users", "admin_users" }`

---

## Profile (Avatar)

### GET `profile/avatar/`
**Auth:** Yes
**200:** `{ "message", "status": "success", "data": { "profile_picture_url" } }`

### POST `profile/avatar/`
**Auth:** Yes · **Content-Type:** `multipart/form-data` · **Body:** `profile_picture: <file>`
**200:** `{ "message": "Avatar updated successfully", "status": "success", "data": { "profile_picture_url" } }`

### DELETE `profile/avatar/`
**Auth:** Yes
**200:** `{ "message": "Avatar deleted successfully", "status": "success" }`

---

## User Contacts

### GET `user-contacts/`
**Auth:** Yes
**200:** `[ { "id", "address_line1", "address_line2", "city", "state", "postal_code", "country", "country_name", "contact_info": {}, "timezone", "availability" } ]`

### POST `user-contacts/`
**Auth:** Yes · **Body:** `{ "address_line1", "address_line2"?, "city", "state", "postal_code", "country", "contact_info"?, "timezone"?, "availability"? }`
**201:** Created contact object

### GET `user-contacts/{id}/`
**Auth:** Yes · **200:** Contact object

### PATCH `user-contacts/{id}/`
**Auth:** Yes · **Body:** (any subset) · **200:** Updated contact object

### DELETE `user-contacts/{id}/`
**Auth:** Yes · **204:** No content
// app/(app)/documents/[id]/page.jsx
export default async function DocumentDetailPage({ params }) {
    const { id } = await params;
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Document Detail</h1>
      <p className="text-gray-500">
              Document {id} — chunks, status, reprocess — Phase 2.
      </p>
    </div>
  );
}
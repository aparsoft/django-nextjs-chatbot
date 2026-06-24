// app/(app)/documents/[id]/page.jsx
export default function DocumentDetailPage({ params }) {
  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Document Detail</h1>
      <p className="text-gray-500">
        Document {params.id} — chunks, status, reprocess — Phase 2.
      </p>
    </div>
  );
}
import { HistoryDetailClient } from "@/components/research/history-detail-client";

export default async function HistoryDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <HistoryDetailClient reportId={id} />;
}

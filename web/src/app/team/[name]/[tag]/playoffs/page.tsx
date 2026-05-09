import { notFound } from "next/navigation";

import { ApiError, fetchTeamMatches } from "@/lib/api";

import { PlayoffStatus } from "./PlayoffStatus";

type PageProps = {
  params: Promise<{ name: string; tag: string }>;
};

export default async function TeamPlayoffsPage({ params }: PageProps) {
  const { name: rawName, tag: rawTag } = await params;
  const name = decodeURIComponent(rawName);
  const tag = decodeURIComponent(rawTag);

  let data;
  try {
    data = await fetchTeamMatches(name, tag);
  } catch (e) {
    if (e instanceof ApiError && e.kind === "not_found") notFound();
    throw e;
  }

  return <PlayoffStatus matches={data.matches} />;
}

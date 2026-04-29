import { writeFile } from "fs/promises";
import path from "path";

import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PLAYERS_DIR = path.join(process.cwd(), "public", "players");

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ puuid: string }> },
) {
  const { puuid } = await params;

  // Validate puuid (alphanumeric + hyphens only)
  if (!/^[a-f0-9-]{36}$/.test(puuid)) {
    return NextResponse.json({ error: "Invalid puuid" }, { status: 400 });
  }

  const form = await req.formData();
  const file = form.get("file");

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "No file provided" }, { status: 400 });
  }

  // Accept only images
  if (!file.type.startsWith("image/")) {
    return NextResponse.json({ error: "File must be an image" }, { status: 400 });
  }

  // Max 5 MB
  if (file.size > 5 * 1024 * 1024) {
    return NextResponse.json({ error: "File too large (max 5 MB)" }, { status: 400 });
  }

  const buffer = Buffer.from(await file.arrayBuffer());
  const filePath = path.join(PUBLIC_PLAYERS_DIR, `${puuid}.png`);

  await writeFile(filePath, buffer);

  return NextResponse.json({ ok: true, path: `/players/${puuid}.png` });
}

/**
 * Agent name → display metadata for the scoreboard.
 *
 * UUIDs come from `valorant-api.com`, which serves agent display icons via:
 *   https://media.valorant-api.com/agents/{uuid}/displayicon.png
 *
 * Names are matched case-insensitively against the `agent` field returned by
 * HenrikDev. Unknown agents fall back to a monogram badge in the UI.
 */

export type AgentRole = "duelist" | "initiator" | "controller" | "sentinel";

type AgentInfo = {
  uuid: string;
  role: AgentRole;
};

const AGENTS: Record<string, AgentInfo> = {
  // Duelists
  jett:    { uuid: "add6443a-41bd-e414-f6ad-e58d267f4e95", role: "duelist" },
  phoenix: { uuid: "eb93336a-449b-9c1b-0a54-a891f7921d69", role: "duelist" },
  reyna:   { uuid: "a3bfb853-43b2-7238-a4f1-ad90e9e46bcc", role: "duelist" },
  raze:    { uuid: "f94c3b30-42be-e959-889c-5aa313dba261", role: "duelist" },
  yoru:    { uuid: "7f94d92c-4234-0a36-9646-3a87eb8b5c89", role: "duelist" },
  neon:    { uuid: "bb2a4828-46eb-8cd1-e765-15848195d751", role: "duelist" },
  iso:     { uuid: "0e38b510-41a8-5780-5e8f-568b2a4f2d6c", role: "duelist" },
  waylay:  { uuid: "df1cb487-4902-002e-5c17-d28e83e78588", role: "duelist" },

  // Initiators
  sova:    { uuid: "320b2a48-4d9b-a075-30f1-1f93a9b638fa", role: "initiator" },
  skye:    { uuid: "6f2a04ca-43e0-be17-7f36-b3908627744d", role: "initiator" },
  breach:  { uuid: "5f8d3a7f-467b-97f3-062c-13acf203c006", role: "initiator" },
  "kay/o": { uuid: "601dbbe7-43ce-be57-2a40-4abd24953621", role: "initiator" },
  kayo:    { uuid: "601dbbe7-43ce-be57-2a40-4abd24953621", role: "initiator" },
  fade:    { uuid: "dade69b4-4f5a-8528-247b-219e5a1facd6", role: "initiator" },
  gekko:   { uuid: "e370fa57-4757-3604-3648-499e1f642d3f", role: "initiator" },
  tejo:    { uuid: "b444168c-4e35-8076-db47-ef9bf368f384", role: "initiator" },

  // Controllers
  brimstone: { uuid: "9f0d8ba9-4140-b941-57d3-a7ad57c6b417", role: "controller" },
  omen:      { uuid: "8e253930-4c05-31dd-1b6c-968525494517", role: "controller" },
  viper:     { uuid: "707eab51-4836-f488-046a-cda6bf494859", role: "controller" },
  astra:     { uuid: "41fb69c1-4189-7b37-f117-bcaf1e96f1bf", role: "controller" },
  harbor:    { uuid: "95b78ed7-4637-86d9-7e41-71ba8c293152", role: "controller" },
  clove:     { uuid: "1dbf2edd-4729-0984-3115-daa5eed44993", role: "controller" },
  miks:      { uuid: "7c8a4701-4de6-9355-b254-e09bc2a34b72", role: "controller" },

  // Sentinels
  cypher:    { uuid: "117ed9e3-49f3-6512-3ccf-0cada7e3823b", role: "sentinel" },
  killjoy:   { uuid: "1e58de9c-4950-5125-93e9-a0aee9f98746", role: "sentinel" },
  sage:      { uuid: "569fdd95-4d10-43ab-ca70-79becc718b46", role: "sentinel" },
  chamber:   { uuid: "22697a3d-45bf-8dd7-4fec-84a9e28c69d7", role: "sentinel" },
  deadlock:  { uuid: "cc8b64c8-4b25-4ff9-6e7f-37b4da43d235", role: "sentinel" },
  vyse:      { uuid: "efba5359-4016-a1e5-7626-b1ae76895940", role: "sentinel" },
  veto:      { uuid: "92eeef5d-43b5-1d4a-8d03-b3927a09034b", role: "sentinel" },
};

const ROLE_BG: Record<AgentRole, string> = {
  duelist: "bg-rose-500/20 text-rose-300 border-rose-500/30",
  initiator: "bg-amber-500/20 text-amber-300 border-amber-500/30",
  controller: "bg-violet-500/20 text-violet-300 border-violet-500/30",
  sentinel: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
};

export function lookupAgent(name: string | null | undefined): AgentInfo | null {
  if (!name) return null;
  return AGENTS[name.toLowerCase()] ?? null;
}

export function agentIconUrl(name: string | null | undefined): string | null {
  const info = lookupAgent(name);
  if (!info) return null;
  return `https://media.valorant-api.com/agents/${info.uuid}/displayicon.png`;
}

export function roleClasses(name: string | null | undefined): string {
  const info = lookupAgent(name);
  if (!info) return "bg-white/5 text-muted-strong border-border";
  return ROLE_BG[info.role];
}

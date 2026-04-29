/**
 * Static staff configuration for teams.
 * Key: "{name}#{tag}" (case-sensitive, matches DB values).
 */

export type StaffEntry = {
  name: string;
  role: string;
  flags?: string[];
};

const TEAM_STAFF: Record<string, StaffEntry[]> = {
  "120pingがIGL#120": [{ name: "noncepolice", role: "Head Coach", flags: ["my", "nz"] }],
};

export function getTeamStaff(name: string, tag: string): StaffEntry[] {
  return TEAM_STAFF[`${name}#${tag}`] ?? [];
}

const TEAM_ICONS: Record<string, string> = {
  "120pingがIGL#120": "/team-icon-120ping.png",
};

export function getTeamIcon(name: string, tag: string): string | null {
  return TEAM_ICONS[`${name}#${tag}`] ?? null;
}

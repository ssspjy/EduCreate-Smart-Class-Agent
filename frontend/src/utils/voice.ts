export const appendVoiceText = (current: string, transcript: string): string => {
  const next = transcript.trim();
  if (!next) return current;
  const prefix = current.trim() ? `${current.trim()} ` : "";
  return `${prefix}${next}`;
};

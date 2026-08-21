import type { Material, MaterialChunk } from "../services/api";

export const SUPPORTED_FILE_ACCEPT = ".pdf,.pptx,.docx,.md,.txt,.jpg,.jpeg,.png,.mp4,.webm,.wav,.m4a,.mp3,.ogg";

export const isMaterialUsable = (material: Material): boolean =>
  material.status !== "failed" && material.status !== "error";

export const getChunkSourceLabel = (chunk: MaterialChunk): string | null => {
  if (chunk.page_ref != null) return `第 ${chunk.page_ref} 页`;
  const timestamp = chunk.media_ref?.match(/#t=([\d.]+)-([\d.]+)/);
  return timestamp ? `${timestamp[1]}–${timestamp[2]} 秒` : null;
};

import { describe, expect, it } from "vitest";
import type { Material, MaterialChunk } from "../services/api";
import { getChunkSourceLabel, isMaterialUsable, SUPPORTED_FILE_ACCEPT } from "./materials";

const material = (status: Material["status"]): Material => ({
  file_id: "material-1",
  filename: "lesson.pdf",
  status,
});

describe("material upload helpers", () => {
  it("keeps uploaded and parsed materials available to the workflow", () => {
    expect(isMaterialUsable(material("uploaded"))).toBe(true);
    expect(isMaterialUsable(material("parsed"))).toBe(true);
    expect(isMaterialUsable(material("failed"))).toBe(false);
    expect(isMaterialUsable(material("error"))).toBe(false);
  });

  it("exposes image and video extensions in the file picker", () => {
    expect(SUPPORTED_FILE_ACCEPT).toContain(".png");
    expect(SUPPORTED_FILE_ACCEPT).toContain(".jpg");
    expect(SUPPORTED_FILE_ACCEPT).toContain(".mp4");
  });

  it("formats PDF pages and video timestamps", () => {
    const base: MaterialChunk = {
      id: "chunk-1",
      material_id: "material-1",
      chunk_index: 0,
      content: "content",
      page_ref: null,
      media_ref: null,
      modality: "text",
      token_count: 1,
    };

    expect(getChunkSourceLabel({ ...base, page_ref: 3 })).toBe("第 3 页");
    expect(getChunkSourceLabel({ ...base, media_ref: "video.mp4#t=0.4-2.1" })).toBe("0.4–2.1 秒");
    expect(getChunkSourceLabel(base)).toBeNull();
  });
});

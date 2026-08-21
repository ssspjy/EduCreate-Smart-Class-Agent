import { describe, expect, it } from "vitest";
import { appendVoiceText } from "./voice";

describe("voice input helpers", () => {
  it("appends recognized text without creating leading whitespace", () => {
    expect(appendVoiceText("请准备一节", "物理课")).toBe("请准备一节 物理课");
    expect(appendVoiceText("", "  物理课  ")).toBe("物理课");
  });

  it("ignores an empty recognition result", () => {
    expect(appendVoiceText("已有内容", "   ")).toBe("已有内容");
  });
});

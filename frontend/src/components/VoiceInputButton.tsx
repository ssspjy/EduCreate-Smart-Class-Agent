import { useEffect, useRef, useState } from "react";
import { Button, Space, Tooltip, Typography } from "antd";
import { AudioOutlined, LoadingOutlined, StopOutlined } from "@ant-design/icons";

type VoiceStatus = "idle" | "listening" | "recording" | "processing" | "error";

interface VoiceInputButtonProps {
  disabled?: boolean;
  onTranscript: (transcript: string) => void;
  onRecordingComplete: (file: File) => Promise<void>;
}

const { Text } = Typography;

const getRecognitionConstructor = (): (new () => EduSpeechRecognition) | undefined =>
  window.SpeechRecognition || window.webkitSpeechRecognition;

export default function VoiceInputButton({
  disabled = false,
  onTranscript,
  onRecordingComplete,
}: VoiceInputButtonProps) {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<EduSpeechRecognition | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  useEffect(() => () => {
    recognitionRef.current?.stop();
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  const startRecorder = async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setStatus("error");
      setError("当前浏览器不支持语音识别或录音，请直接输入文字");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      streamRef.current = stream;
      recorderRef.current = recorder;
      audioChunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || "audio/webm" });
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        recorderRef.current = null;
        setStatus("processing");
        const extension = blob.type.includes("wav")
          ? "wav"
          : blob.type.includes("mp4") ? "m4a" : "webm";
        void onRecordingComplete(new File([blob], `voice-${Date.now()}.${extension}`, {
          type: blob.type || "audio/webm",
        }))
          .then(() => setStatus("idle"))
          .catch((reason: unknown) => {
            setStatus("error");
            setError(reason instanceof Error ? reason.message : "录音转写失败");
          });
      };
      recorder.start();
      setError(null);
      setStatus("recording");
    } catch (reason: unknown) {
      setStatus("error");
      setError(reason instanceof Error ? reason.message : "无法访问麦克风，请检查浏览器权限");
    }
  };

  const startSpeechRecognition = () => {
    const Recognition = getRecognitionConstructor();
    if (!Recognition) {
      void startRecorder();
      return;
    }
    const recognition = new Recognition();
    recognition.lang = "zh-CN";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      const transcripts: string[] = [];
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        if (event.results[index].isFinal) transcripts.push(event.results[index][0].transcript);
      }
      transcripts.forEach(onTranscript);
    };
    recognition.onerror = (event) => {
      setStatus("error");
      setError(event.error === "not-allowed" ? "麦克风权限被拒绝，请允许浏览器访问麦克风" : `语音识别失败：${event.error}`);
    };
    recognition.onend = () => setStatus((current) => current === "listening" ? "idle" : current);
    recognitionRef.current = recognition;
    setError(null);
    setStatus("listening");
    recognition.start();
  };

  const stop = () => {
    if (status === "listening") {
      recognitionRef.current?.stop();
      return;
    }
    if (status === "recording") recorderRef.current?.stop();
  };

  const active = status === "listening" || status === "recording";
  const label = status === "recording" ? "停止录音" : status === "listening" ? "停止识别" : "语音输入";

  return (
    <Space direction="vertical" size={2}>
      <Tooltip title={active ? label : "优先使用浏览器实时识别，不支持时自动录音转写"}>
        <Button
          type={active ? "primary" : "default"}
          danger={active}
          icon={status === "processing" ? <LoadingOutlined /> : active ? <StopOutlined /> : <AudioOutlined />}
          onClick={active ? stop : startSpeechRecognition}
          disabled={disabled || status === "processing"}
          aria-label={label}
        >
          {label}
        </Button>
      </Tooltip>
      {status === "processing" && <Text type="secondary" style={{ fontSize: 11 }}>正在上传录音并转写…</Text>}
      {error && <Text type="warning" style={{ fontSize: 11, maxWidth: 220 }}>{error}</Text>}
    </Space>
  );
}

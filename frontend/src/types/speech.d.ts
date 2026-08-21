interface EduSpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

interface EduSpeechRecognitionResult {
  readonly isFinal: boolean;
  readonly length: number;
  [index: number]: EduSpeechRecognitionAlternative;
}

interface EduSpeechRecognitionResultList {
  readonly length: number;
  [index: number]: EduSpeechRecognitionResult;
}

interface EduSpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: EduSpeechRecognitionResultList;
}

interface EduSpeechRecognitionErrorEvent extends Event {
  readonly error: string;
  readonly message: string;
}

interface EduSpeechRecognition extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: EduSpeechRecognitionEvent) => void) | null;
  onerror: ((event: EduSpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

interface Window {
  SpeechRecognition?: new () => EduSpeechRecognition;
  webkitSpeechRecognition?: new () => EduSpeechRecognition;
}

/**
 * Audio Recorder Worklet
 */

let micStream;

export async function startAudioRecorderWorklet(audioRecorderHandler) {
  // Create an AudioContext
  const audioRecorderContext = new AudioContext({ sampleRate: 16000 });
  console.log("AudioContext sample rate:", audioRecorderContext.sampleRate);

  // Load the AudioWorklet module
  const workletURL = new URL("./pcm-recorder-processor.js", import.meta.url);
  await audioRecorderContext.audioWorklet.addModule(workletURL);

  // Request access to the microphone (with fallback for older browsers/contexts)
  micStream = await getUserMediaCompat({
    audio: { channelCount: 1 },
  });
  const source = audioRecorderContext.createMediaStreamSource(micStream);

  // Create an AudioWorkletNode that uses the PCMProcessor
  const audioRecorderNode = new AudioWorkletNode(
    audioRecorderContext,
    "pcm-recorder-processor"
  );

  // Connect the microphone source to the worklet.
  source.connect(audioRecorderNode);
  audioRecorderNode.port.onmessage = (event) => {
    // Convert to 16-bit PCM
    const pcmData = convertFloat32ToPCM(event.data);

    // Send the PCM data to the handler.
    audioRecorderHandler(pcmData);
  };
  return [audioRecorderNode, audioRecorderContext, micStream];
}

/**
 * Stop the microphone.
 */
export function stopMicrophone(micStream) {
  micStream.getTracks().forEach((track) => track.stop());
  console.log("stopMicrophone(): Microphone stopped.");
}

// Convert Float32 samples to 16-bit PCM.
function convertFloat32ToPCM(inputData) {
  // Create an Int16Array of the same length.
  const pcm16 = new Int16Array(inputData.length);
  for (let i = 0; i < inputData.length; i++) {
    // Multiply by 0x7fff (32767) to scale the float value to 16-bit PCM range.
    pcm16[i] = inputData[i] * 0x7fff;
  }
  // Return the underlying ArrayBuffer.
  return pcm16.buffer;
}

async function getUserMediaCompat(constraints) {
  if (navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === "function") {
    return navigator.mediaDevices.getUserMedia(constraints);
  }

  const legacyGetUserMedia =
    navigator.getUserMedia ||
    navigator.webkitGetUserMedia ||
    navigator.mozGetUserMedia ||
    navigator.msGetUserMedia;

  if (!legacyGetUserMedia) {
    throw new Error(
      "Microphone access is unavailable in this browser/context. " +
      "Use latest Chrome/Edge and open via http://localhost:8000."
    );
  }

  return new Promise((resolve, reject) => {
    legacyGetUserMedia.call(navigator, constraints, resolve, reject);
  });
}

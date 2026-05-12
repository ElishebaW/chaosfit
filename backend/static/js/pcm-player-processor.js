/**
 * An audio worklet processor that stores the PCM audio data sent from the main thread
 * to a buffer and plays it. Supports an optional delay to align corrections with the
 * video frame that triggered them (set via { command: 'setDelay', delaySeconds: N }).
 */
class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    // Init buffer
    this.bufferSize = 24000 * 180;  // 24kHz x 180 seconds
    this.buffer = new Float32Array(this.bufferSize);
    this.writeIndex = 0;
    this.readIndex = 0;

    this.delaySeconds = 0;
    this.pendingQueue = [];  // [{floats: Float32Array, playAt: number}]

    // Handle incoming messages from main thread
    this.port.onmessage = (event) => {
      if (event.data.command === 'endOfAudio') {
        this.readIndex = this.writeIndex;
        this.pendingQueue = [];
        console.log("endOfAudio received, clearing the buffer.");
        return;
      }

      if (event.data.command === 'setDelay') {
        this.delaySeconds = Math.max(0, event.data.delaySeconds || 0);
        return;
      }

      const int16Samples = new Int16Array(event.data);

      if (this.delaySeconds <= 0) {
        this._enqueue(int16Samples);
      } else {
        const floats = new Float32Array(int16Samples.length);
        for (let i = 0; i < int16Samples.length; i++) {
          floats[i] = int16Samples[i] / 32768;
        }
        this.pendingQueue.push({ floats, playAt: currentTime + this.delaySeconds });
      }
    };
  }

  // Push incoming Int16 data into our ring buffer.
  _enqueue(int16Samples) {
    for (let i = 0; i < int16Samples.length; i++) {
      // Convert 16-bit integer to float in [-1, 1]
      const floatVal = int16Samples[i] / 32768;

      // Store in ring buffer for left channel only (mono)
      this.buffer[this.writeIndex] = floatVal;
      this.writeIndex = (this.writeIndex + 1) % this.bufferSize;

      // Overflow handling (overwrite oldest samples)
      if (this.writeIndex === this.readIndex) {
        this.readIndex = (this.readIndex + 1) % this.bufferSize;
      }
    }
  }

  // Push pre-converted float data into the ring buffer.
  _enqueueFloats(floats) {
    for (let i = 0; i < floats.length; i++) {
      this.buffer[this.writeIndex] = floats[i];
      this.writeIndex = (this.writeIndex + 1) % this.bufferSize;
      if (this.writeIndex === this.readIndex) {
        this.readIndex = (this.readIndex + 1) % this.bufferSize;
      }
    }
  }

  // The system calls `process()` ~128 samples at a time (depending on the browser).
  // We flush delayed audio whose scheduled time has arrived, then fill the output.
  process(inputs, outputs, parameters) {
    // Flush pending audio items whose scheduled playback time has arrived.
    while (this.pendingQueue.length > 0 && currentTime >= this.pendingQueue[0].playAt) {
      this._enqueueFloats(this.pendingQueue.shift().floats);
    }

    // Write a frame to the output
    const output = outputs[0];
    const framesPerBlock = output[0].length;
    for (let frame = 0; frame < framesPerBlock; frame++) {

      // Write the sample(s) into the output buffer
      output[0][frame] = this.buffer[this.readIndex]; // left channel
      if (output.length > 1) {
        output[1][frame] = this.buffer[this.readIndex]; // right channel
      }

      // Move the read index forward unless underflowing
      if (this.readIndex != this.writeIndex) {
        this.readIndex = (this.readIndex + 1) % this.bufferSize;
      }
    }

    // Returning true tells the system to keep the processor alive
    return true;
  }
}

registerProcessor('pcm-player-processor', PCMPlayerProcessor);

const lectureState = {
  lectureId: null,
  studentId: null,
  subject: null,
  topic: null,
  roomUrl: null,
  token: null,
  isMock: false,
  notes: [],
  outline: [],
  transcript: [],
  room: null,
  micEnabled: true,
  camEnabled: true,
  recognition: null,
  mockLectureStarted: false,
};

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function setStatus(text, type = "") {
  $("connectionStatus").textContent = text;
  $("connectionStatus").className = `pill ${type}`;
}

function appendTranscript(speaker, text) {
  lectureState.transcript.push({ speaker, text, at: new Date().toISOString() });
  const line = document.createElement("p");
  line.className = "transcript-line";
  line.innerHTML = `<strong>${escapeHtml(speaker)}:</strong> ${escapeHtml(text)}`;
  $("liveTranscript").prepend(line);
}

function renderNotes() {
  $("lectureOutline").innerHTML = lectureState.outline
    .map((step) => `<li>${escapeHtml(step)}</li>`)
    .join("");
  $("lectureNotes").innerHTML = lectureState.notes
    .map(
      (note) => `
      <article class="note-card">
        <strong>${escapeHtml(note.title)}</strong>
        <span class="pill">${escapeHtml(note.source)}</span>
        <p>${escapeHtml(note.snippet)}</p>
      </article>
    `,
    )
    .join("");
}

function setTutorSpeaking(active) {
  $("tutorAvatar").classList.toggle("speaking", active);
  $("tutorStatus").textContent = active ? "AI tutor speaking…" : "Listening — speak to interject";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || response.statusText);
  }
  return response.json();
}

function loadSession() {
  const raw = sessionStorage.getItem("tutorloopLecture");
  if (!raw) {
    throw new Error("No active lecture session. Start one from the AI Tutor tab.");
  }
  const session = JSON.parse(raw);
  Object.assign(lectureState, {
    lectureId: session.lecture_id,
    studentId: session.student_id,
    subject: session.subject,
    topic: session.topic,
    roomUrl: session.room_url,
    token: session.token,
    isMock: session.is_mock,
    notes: session.notes || [],
    outline: session.lecture_outline || [],
  });
  $("lectureTitle").textContent = `${session.subject} — ${session.topic}`;
  $("lectureSubtitle").textContent = session.is_mock
    ? "Browser lecture mode (start the LiveKit agent for full voice AI)"
    : "LiveKit voice + video session with virtual tutor";
  renderNotes();
}

async function connectLiveKit() {
  const LK = window.LivekitClient || window.livekit;
  if (!LK) throw new Error("LiveKit client failed to load");
  const { Room, RoomEvent, Track } = LK;
  const room = new Room({ adaptiveStream: true, dynacast: true });
  lectureState.room = room;

  room.on(RoomEvent.Connected, () => setStatus("Connected", "tutor"));
  room.on(RoomEvent.Disconnected, () => setStatus("Disconnected"));
  room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
    const agentSpeaking = speakers.some(
      (participant) => participant.identity !== lectureState.studentId && !participant.isLocal,
    );
    setTutorSpeaking(agentSpeaking);
  });
  room.on(RoomEvent.TrackSubscribed, (track, _publication, participant) => {
    if (track.kind === Track.Kind.Audio && !participant.isLocal) {
      const audioEl = track.attach();
      $("agentAudio").appendChild(audioEl);
    }
  });
  room.on(RoomEvent.LocalTrackPublished, (publication) => {
    if (publication.source === Track.Source.Camera && publication.videoTrack) {
      publication.videoTrack.attach($("studentVideo"));
    }
  });
  room.on(RoomEvent.TranscriptionReceived, (segments) => {
    for (const segment of segments) {
      if (!segment.text?.trim()) continue;
      const speaker = segment.participantInfo?.identity === lectureState.studentId ? "Student" : "AI Tutor";
      appendTranscript(speaker, segment.text.trim());
    }
  });

  await room.connect(lectureState.roomUrl, lectureState.token);
  await room.localParticipant.setMicrophoneEnabled(true);
  await room.localParticipant.setCameraEnabled(true);
  setStatus("Live lecture", "tutor");
  appendTranscript("System", "Connected to LiveKit. Your virtual tutor will join shortly — speak anytime to interject.");
}

async function startLocalCamera() {
  const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
  $("studentVideo").srcObject = stream;
}

async function toggleMic() {
  if (lectureState.room) {
    lectureState.micEnabled = !lectureState.micEnabled;
    await lectureState.room.localParticipant.setMicrophoneEnabled(lectureState.micEnabled);
  } else if (lectureState.recognition) {
    if (lectureState.micEnabled) {
      lectureState.recognition.stop();
      lectureState.micEnabled = false;
    } else {
      lectureState.recognition.start();
      lectureState.micEnabled = true;
    }
  }
  $("toggleMicBtn").textContent = lectureState.micEnabled ? "Mic on" : "Mic off";
}

async function toggleCam() {
  lectureState.camEnabled = !lectureState.camEnabled;
  if (lectureState.room) {
    await lectureState.room.localParticipant.setCameraEnabled(lectureState.camEnabled);
  }
  $("studentVideo").style.display = lectureState.camEnabled ? "block" : "none";
  $("toggleCamBtn").textContent = lectureState.camEnabled ? "Camera on" : "Camera off";
}

function speak(text) {
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.onstart = () => setTutorSpeaking(true);
    utterance.onend = () => {
      setTutorSpeaking(false);
      resolve();
    };
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  });
}

async function askMockTutor(question) {
  appendTranscript("Student", question);
  const result = await api("/ai/chat", {
    method: "POST",
    body: JSON.stringify({
      student_id: lectureState.studentId,
      question: `During a live lecture on ${lectureState.topic}, the student interjects: ${question}`,
      subject: lectureState.subject,
      language: "English",
    }),
  });
  appendTranscript("AI Tutor", result.answer);
  await speak(result.answer);
}

async function startMockLecture() {
  setStatus("Browser lecture", "note");
  await startLocalCamera();
  await navigator.mediaDevices.getUserMedia({ audio: true });

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    recognition.onresult = async (event) => {
      const last = event.results[event.results.length - 1];
      if (!last.isFinal) return;
      const text = last[0].transcript.trim();
      if (text.length < 3) return;
      window.speechSynthesis.cancel();
      setTutorSpeaking(false);
      await askMockTutor(text);
    };
    recognition.onerror = () => {};
    lectureState.recognition = recognition;
    recognition.start();
  } else {
    $("lectureHint").textContent = "Speech recognition is unavailable in this browser. Type questions in the transcript panel is not enabled; use Chrome for voice interjection.";
  }

  if (lectureState.mockLectureStarted) return;
  lectureState.mockLectureStarted = true;
  const intro = `Welcome to your ${lectureState.subject} lecture on ${lectureState.topic}. I can see your notes on the right. Speak anytime to ask a question and I will pause to answer. Let us begin with the big picture: a derivative measures how fast something changes at one instant.`;
  appendTranscript("AI Tutor", intro);
  await speak(intro);
}

async function endLecture() {
  const transcriptText = lectureState.transcript
    .map((line) => `${line.speaker}: ${line.text}`)
    .reverse()
    .join("\n");
  if (lectureState.room) {
    await lectureState.room.disconnect();
  }
  if (lectureState.recognition) {
    lectureState.recognition.stop();
  }
  window.speechSynthesis?.cancel();
  const result = await api(`/ai/lecture/${lectureState.lectureId}/complete`, {
    method: "POST",
    body: JSON.stringify({
      student_id: lectureState.studentId,
      transcript: transcriptText || "Student completed an AI lecture session.",
    }),
  });
  sessionStorage.setItem(
    "tutorloopLectureComplete",
    JSON.stringify({ conversation_id: result.conversation_id, lecture_id: result.lecture_id }),
  );
  sessionStorage.removeItem("tutorloopLecture");
  alert(result.message);
  window.location.href = "/";
}

function bindEvents() {
  $("toggleMicBtn").addEventListener("click", toggleMic);
  $("toggleCamBtn").addEventListener("click", toggleCam);
  $("endLectureBtn").addEventListener("click", endLecture);
  $("raiseHandBtn").addEventListener("click", () => {
    appendTranscript("Student", "[Raised hand to interject]");
    $("lectureHint").textContent = "Go ahead — ask your question out loud.";
  });
}

async function init() {
  bindEvents();
  loadSession();
  try {
    if (lectureState.isMock || !window.LivekitClient && !window.livekit) {
      await startMockLecture();
    } else {
      await connectLiveKit();
    }
  } catch (error) {
    setStatus("Fallback mode", "note");
    $("lectureSubtitle").textContent = `LiveKit unavailable (${error.message}). Using browser voice mode.`;
    await startMockLecture();
  }
}

init().catch((error) => {
  document.body.insertAdjacentHTML(
    "afterbegin",
    `<div class="output">Lecture error: ${escapeHtml(error.message)}</div>`,
  );
});

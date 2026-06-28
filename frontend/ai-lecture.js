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
  noteIds: [],
  bookIds: [],
  groundedSources: false,
  transcript: [],
  transcriptIndexByKey: new Map(),
  room: null,
  micEnabled: true,
  camEnabled: true,
  isCompleting: false,
  recognition: null,
  recognitionMode: null,
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

function normalizeTranscriptText(text) {
  return String(text ?? "").replace(/\s+/g, " ").trim();
}

function transcriptSegmentKey(segment, speaker) {
  if (segment.id || segment.segmentId || segment.sid) return segment.id || segment.segmentId || segment.sid;
  if (segment.startTime != null || segment.endTime != null) {
    return `${speaker}:${segment.startTime ?? ""}:${segment.endTime ?? ""}:${segment.language ?? ""}`;
  }
  return null;
}

function renderTranscriptLine(entry) {
  entry.element.innerHTML = `<strong>${escapeHtml(entry.speaker)}:</strong> ${escapeHtml(entry.text)}`;
}

function appendTranscript(speaker, text, key = null) {
  const normalizedText = normalizeTranscriptText(text);
  if (!normalizedText) return;

  if (key && lectureState.transcriptIndexByKey.has(key)) {
    const existing = lectureState.transcript[lectureState.transcriptIndexByKey.get(key)];
    if (normalizedText.length >= existing.text.length) {
      existing.text = normalizedText;
      existing.at = new Date().toISOString();
      renderTranscriptLine(existing);
    }
    return;
  }

  const lastIndex = lectureState.transcript.length - 1;
  const last = lectureState.transcript[lastIndex];
  if (last?.speaker === speaker) {
    const previous = normalizeTranscriptText(last.text);
    if (previous === normalizedText) return;
    if (normalizedText.startsWith(previous) || previous.startsWith(normalizedText)) {
      if (normalizedText.length > previous.length) {
        last.text = normalizedText;
        last.at = new Date().toISOString();
        renderTranscriptLine(last);
      }
      return;
    }
  }

  const line = document.createElement("p");
  line.className = "transcript-line";
  const entry = { speaker, text: normalizedText, at: new Date().toISOString(), key, element: line };
  lectureState.transcript.push(entry);
  if (key) lectureState.transcriptIndexByKey.set(key, lectureState.transcript.length - 1);
  renderTranscriptLine(entry);
  $("liveTranscript").prepend(line);
}

function startBrowserTranscription(mode) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return false;
  if (lectureState.recognition) return true;

  const recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-US";
  lectureState.recognitionMode = mode;
  recognition.onresult = async (event) => {
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index];
      const text = result[0]?.transcript?.trim();
      if (!text) continue;
      const key = `student-browser:${index}`;
      appendTranscript("Student", text, key);

      if (lectureState.recognitionMode === "mock" && result.isFinal && text.length >= 3) {
        window.speechSynthesis.cancel();
        setTutorSpeaking(false);
        await askMockTutor(text);
      }
    }
  };
  recognition.onerror = () => {};
  recognition.onend = () => {
    if (!lectureState.micEnabled) return;
    try {
      recognition.start();
    } catch (_error) {
      // Some browsers throw if restarted too quickly.
    }
  };

  lectureState.recognition = recognition;
  recognition.start();
  return true;
}

function stopBrowserTranscription() {
  if (!lectureState.recognition) return;
  try {
    lectureState.recognition.onend = null;
    lectureState.recognition.stop();
  } catch (_error) {
    // Ignore already-stopped state.
  }
  lectureState.recognition = null;
  lectureState.recognitionMode = null;
}

function buildPersistedTranscript() {
  const turns = [];
  for (const line of lectureState.transcript) {
    if (line.speaker === "System") continue;
    const text = normalizeTranscriptText(line.text);
    if (!text) continue;

    const previousTurn = turns[turns.length - 1];
    if (previousTurn?.speaker === line.speaker) {
      if (previousTurn.text === text || previousTurn.text.includes(text)) continue;
      if (text.includes(previousTurn.text)) {
        previousTurn.text = text;
      } else {
        previousTurn.text = `${previousTurn.text} ${text}`;
      }
      continue;
    }
    turns.push({ speaker: line.speaker, text });
  }

  return turns.map((line) => `${line.speaker}: ${line.text}`).join("\n");
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
    noteIds: session.note_ids || [],
    bookIds: session.book_ids || [],
    groundedSources: Boolean(session.grounded_sources),
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
      appendTranscript(speaker, segment.text, transcriptSegmentKey(segment, speaker));
    }
  });

  await room.connect(lectureState.roomUrl, lectureState.token);
  await room.localParticipant.setMicrophoneEnabled(true);
  await room.localParticipant.setCameraEnabled(true);
  startBrowserTranscription("live");
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
    if (lectureState.micEnabled) {
      startBrowserTranscription(lectureState.isMock ? "mock" : "live");
    } else {
      stopBrowserTranscription();
    }
  } else if (lectureState.recognition) {
    if (lectureState.micEnabled) {
      stopBrowserTranscription();
      lectureState.micEnabled = false;
    } else {
      startBrowserTranscription(lectureState.isMock ? "mock" : "live");
      lectureState.micEnabled = true;
    }
  } else if (!lectureState.micEnabled) {
    startBrowserTranscription(lectureState.isMock ? "mock" : "live");
    lectureState.micEnabled = true;
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
  const result = await api("/ai/chat", {
    method: "POST",
    body: JSON.stringify({
      student_id: lectureState.studentId,
      question: `During a live lecture on ${lectureState.topic}, the student interjects: ${question}`,
      subject: lectureState.subject,
      language: "English",
      note_ids: lectureState.noteIds,
      book_ids: lectureState.bookIds,
    }),
  });
  appendTranscript("AI Tutor", result.answer);
  await speak(result.answer);
}

async function startMockLecture() {
  setStatus("Browser lecture", "note");
  await startLocalCamera();
  await navigator.mediaDevices.getUserMedia({ audio: true });

  if (!startBrowserTranscription("mock")) {
    $("lectureHint").textContent = "Speech recognition is unavailable in this browser. Type questions in the transcript panel is not enabled; use Chrome for voice interjection.";
  }

  if (lectureState.mockLectureStarted) return;
  lectureState.mockLectureStarted = true;

  const welcome = `Welcome to your lecture on ${lectureState.topic}. I can see your notes on the right — speak anytime to ask a question and I'll pause to answer.`;
  appendTranscript("AI Tutor", welcome);
  await speak(welcome);

  // Generate a real, topic-specific opening lecture from the backend so ANY
  // topic gets an actual lecture (not a hardcoded calculus intro).
  try {
    const result = await api("/ai/chat", {
      method: "POST",
      body: JSON.stringify({
        student_id: lectureState.studentId,
        question: `Deliver the opening of a short spoken lecture on "${lectureState.topic}"${
          lectureState.subject && lectureState.subject !== lectureState.topic ? ` in ${lectureState.subject}` : ""
        }. Start with the big-picture idea, then teach the first key concept with one example. Keep it conversational for text-to-speech.`,
        subject: lectureState.subject,
        language: "English",
        note_ids: lectureState.noteIds,
        book_ids: lectureState.bookIds,
      }),
    });
    appendTranscript("AI Tutor", result.answer);
    await speak(result.answer);
  } catch (error) {
    const fallback = `Let's begin with the big picture of ${lectureState.topic}. I'll explain the core idea step by step — ask me anything as we go.`;
    appendTranscript("AI Tutor", fallback);
    await speak(fallback);
  }
}

async function endLecture() {
  if (lectureState.isCompleting) return;
  lectureState.isCompleting = true;
  $("endLectureBtn").textContent = "Saving...";
  $("endLectureBtn").disabled = true;
  try {
    const transcriptText = buildPersistedTranscript();
    if (lectureState.room) {
      await lectureState.room.disconnect();
    }
    if (lectureState.recognition) {
      stopBrowserTranscription();
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
  } catch (error) {
    lectureState.isCompleting = false;
    $("endLectureBtn").textContent = "End & save";
    $("endLectureBtn").disabled = false;
    $("lectureHint").textContent = `Could not save lecture: ${error.message || error}`;
  }
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

const state = {
  studentId: "student-demo-maya",
  tutorId: "tutor-demo-elena",
  bookingId: "booking-demo-derivatives",
  sessionId: "session-demo-derivatives",
  conversationId: null,
  isAskingAi: false,
  notes: [],
  books: [],
  tutors: [],
};

const sectionTitles = {
  home: "Learning Loop",
  notes: "Notes Marketplace",
  booking: "Tutor Booking",
  classroom: "Live Classroom",
  ai: "AI Tutor",
  recommendations: "Recommendations",
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof error.detail === "string" ? error.detail : error.detail?.message || response.statusText);
  }
  return response.json();
}

function setSection(sectionId) {
  document.querySelectorAll(".section").forEach((section) => section.classList.toggle("active", section.id === sectionId));
  document.querySelectorAll(".nav-tabs button").forEach((button) => button.classList.toggle("active", button.dataset.section === sectionId));
  $("sectionTitle").textContent = sectionTitles[sectionId] || "TutorLoop";
}

function showError(target, error) {
  target.textContent = `Error: ${error.message || error}`;
}

function pill(text, type = "") {
  return `<span class="pill ${type}">${escapeHtml(text)}</span>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderResults(target, results) {
  if (!results.length) {
    target.innerHTML = $("emptyTemplate").innerHTML;
    return;
  }
  target.innerHTML = results
    .map(
      (item) => `
        <article class="result-item">
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.snippet || item.description || item.reason || "")}</p>
          <div class="meta-row">
            ${pill(item.collection || item.content_type, item.content_type)}
            ${item.subject ? pill(item.subject) : ""}
            ${pill(`score ${Number(item.score || 0).toFixed(2)}`)}
          </div>
        </article>
      `,
    )
    .join("");
}

function renderNotes(notes) {
  $("notesCount").textContent = notes.length;
  $("notesResults").innerHTML = notes
    .map(
      (note) => `
      <article class="data-card">
        <strong>${escapeHtml(note.title)}</strong>
        <p>${escapeHtml(note.description)}</p>
        <div class="meta-row">
          ${pill(note.subject)}
          ${pill(`$${Number(note.price).toFixed(2)}`, "note")}
          ${pill(`${Number(note.rating || 0).toFixed(1)} rating`)}
        </div>
        <button data-buy-note="${escapeHtml(note.id || note._id)}">Buy note</button>
      </article>
    `,
    )
    .join("");
}

function renderBooks(books) {
  $("booksResults").innerHTML = books
    .map(
      (book) => `
      <article class="data-card">
        <strong>${escapeHtml(book.title)}</strong>
        <p>${escapeHtml(book.description)}</p>
        <div class="meta-row">
          ${pill(book.subject, "book")}
          ${pill(book.author || "Platform", "tutor")}
          ${pill(`${Number(book.rating || 0).toFixed(1)} rating`)}
        </div>
        <button data-add-book="${escapeHtml(book.id)}">Add to library</button>
      </article>
    `,
    )
    .join("");
}

function renderTutors(tutors) {
  $("tutorsCount").textContent = tutors.length;
  $("tutorResults").innerHTML = tutors
    .map(
      (tutor) => `
      <article class="data-card">
        <strong>${escapeHtml(tutor.display_name)}</strong>
        <p>${escapeHtml(tutor.bio)}</p>
        <div class="meta-row">
          ${pill((tutor.subjects || []).join(", "), "tutor")}
          ${pill(`$${Number(tutor.hourly_rate).toFixed(0)}/hr`)}
          ${pill(`${Number(tutor.rating || 0).toFixed(1)} rating`)}
        </div>
        <p>${escapeHtml(tutor.teaching_style)}</p>
        <button data-book-tutor="${escapeHtml(tutor.id || tutor._id)}">Book tutor</button>
      </article>
    `,
    )
    .join("");
}

function renderRecommendations(recs) {
  $("recsCount").textContent = recs.length;
  $("recommendationsList").innerHTML = recs
    .map(
      (rec) => `
      <article class="data-card">
        <strong>${escapeHtml(rec.title)}</strong>
        <p>${escapeHtml(rec.reason)}</p>
        <div class="meta-row">
          ${pill(rec.type, rec.type)}
          ${rec.subject ? pill(rec.subject) : ""}
          ${pill(`score ${Number(rec.score || 0).toFixed(2)}`)}
        </div>
      </article>
    `,
    )
    .join("");
}

async function loadHealth() {
  const health = await api("/health");
  $("mongoStatus").textContent = `MongoDB: ${health.mongo}`;
  $("geminiStatus").textContent = `Gemini: ${health.gemini}`;
  $("livekitStatus").textContent = `LiveKit: ${health.livekit}`;
}

async function loadDemoIds() {
  const ids = await api("/demo/ids");
  state.studentId = ids.student_id;
  state.tutorId = ids.tutor_id;
  state.bookingId = ids.booking_id;
  state.sessionId = ids.session_id;
  $("demoStudent").textContent = ids.student_id;
}

async function searchSemantic() {
  const target = $("semanticResults");
  target.innerHTML = "";
  try {
    const query = encodeURIComponent($("mainSearchInput").value);
    const results = await api(`/search?q=${query}&limit=8`);
    renderResults(target, results);
  } catch (error) {
    showError(target, error);
  }
}

async function searchNotes() {
  try {
    const query = encodeURIComponent($("noteQuery").value);
    const subject = encodeURIComponent($("noteSubject").value);
    const maxPrice = encodeURIComponent($("noteMaxPrice").value);
    state.notes = await api(`/notes/search?q=${query}&subject=${subject}&max_price=${maxPrice}`);
    renderNotes(state.notes);
  } catch (error) {
    showError($("notesResults"), error);
  }
}

async function searchTutors() {
  try {
    const query = encodeURIComponent($("tutorQuery").value);
    const subject = encodeURIComponent($("tutorSubject").value);
    state.tutors = await api(`/tutors/search?q=${query}&subject=${subject}`);
    renderTutors(state.tutors);
  } catch (error) {
    showError($("tutorResults"), error);
  }
}

async function searchBooks() {
  try {
    const query = encodeURIComponent($("bookQuery").value);
    const subject = encodeURIComponent($("bookSubject").value);
    state.books = await api(`/books/search?q=${query}&subject=${subject}`);
    if (!state.books.length) {
      state.books = await api("/books");
    }
    renderBooks(state.books);
  } catch (error) {
    showError($("booksResults"), error);
  }
}

async function addBook(bookId) {
  const result = await api(`/books/${bookId}/access`, {
    method: "POST",
    body: JSON.stringify({ student_id: state.studentId }),
  });
  await loadRecommendations();
  alert(result.message);
}

async function purchaseNote(noteId) {
  const result = await api(`/notes/${noteId}/purchase`, {
    method: "POST",
    body: JSON.stringify({ student_id: state.studentId }),
  });
  await loadRecommendations();
  alert(result.message);
}

async function bookTutor(tutorId) {
  const requestedStart = new Date($("bookingTime").value || Date.now() + 60 * 60 * 1000);
  const availableSlots = await api(`/tutors/${tutorId}/availability?limit=10`);
  if (!availableSlots.length) {
    throw new Error("This tutor has no open 30-minute slots.");
  }
  const exactSlot = availableSlots.find((slot) => new Date(slot.starts_at).getTime() === requestedStart.getTime());
  const slot = exactSlot || availableSlots[0];
  const startsAt = new Date(slot.starts_at).toISOString();
  $("bookingTime").value = startsAt.slice(0, 16);
  const booking = await api("/bookings", {
    method: "POST",
    body: JSON.stringify({
      tutor_id: tutorId,
      student_id: state.studentId,
      subject: slot.subject || $("tutorSubject").value || "Calculus",
      starts_at: startsAt,
      duration_minutes: 30,
    }),
  });
  state.tutorId = tutorId;
  state.bookingId = booking.id || booking._id;
  state.sessionId = booking.session_id;
  $("bookingResult").textContent = `Booked 30 minutes of ${booking.subject} at ${new Date(booking.starts_at).toLocaleString()} with room ${booking.room_id}. Session ${booking.session_id}.`;
  setSection("classroom");
}

async function joinRoom() {
  const target = $("roomTokenOutput");
  try {
    const result = await api("/livekit/token", {
      method: "POST",
      body: JSON.stringify({
        booking_id: state.bookingId,
        user_id: state.studentId,
        display_name: "Maya Chen",
      }),
    });
    target.innerHTML = `Room: ${escapeHtml(result.room_id)}
Token: ${escapeHtml(result.token)}
Mode: ${result.is_mock ? "mock LiveKit token" : "real LiveKit token"}

<a class="link-button" href="${escapeHtml(result.room_url)}" target="_blank" rel="noreferrer">Open classroom</a>`;
  } catch (error) {
    showError(target, error);
  }
}

async function reflectSession() {
  const target = $("reflectionOutput");
  try {
    const result = await api(`/sessions/${state.sessionId}/reflect`, {
      method: "POST",
      body: JSON.stringify({
        transcript: $("transcriptInput").value,
        target_language: $("reflectionLanguage").value,
      }),
    });
    target.textContent = [
      `Reflection: ${result.reflection_id}`,
      "",
      result.translated_summary,
      "",
      `Weaknesses: ${result.weaknesses.join(", ")}`,
      `AI instructions: ${result.future_ai_instructions.join(" ")}`,
      `Mode: ${result.is_mock ? "mock Gemini reflection" : "Gemini reflection"}`,
    ].join("\n");
    await loadRecommendations();
    setSection("ai");
  } catch (error) {
    showError(target, error);
  }
}

async function startAiLecture() {
  const target = $("lectureLaunchStatus");
  try {
    target.textContent = "Preparing lecture room and loading notes…";
    const result = await api("/ai/lecture/start", {
      method: "POST",
      body: JSON.stringify({
        student_id: state.studentId,
        subject: $("lectureSubject").value || "Calculus",
        topic: $("lectureTopic").value || "derivatives",
        language: "English",
      }),
    });
    sessionStorage.setItem(
      "tutorloopLecture",
      JSON.stringify({
        lecture_id: result.lecture_id,
        student_id: state.studentId,
        subject: $("lectureSubject").value,
        topic: $("lectureTopic").value,
        room_url: result.room_url,
        token: result.token,
        is_mock: result.is_mock,
        notes: result.notes,
        lecture_outline: result.lecture_outline,
      }),
    );
    window.location.href = "/ai-lecture.html";
  } catch (error) {
    showError(target, error);
  }
}

async function askAi() {
  if (state.isAskingAi) return;
  state.isAskingAi = true;
  $("askAiBtn").disabled = true;
  $("askAiBtn").textContent = "Thinking...";
  const answerTarget = $("aiAnswer");
  const contextTarget = $("aiContext");
  try {
    const result = await api("/ai/chat", {
      method: "POST",
      body: JSON.stringify({
        student_id: state.studentId,
        question: $("aiQuestion").value,
        subject: "Calculus",
        language: "English",
      }),
    });
    state.conversationId = result.conversation_id;
    answerTarget.textContent = result.answer;
    renderResults(contextTarget, result.retrieved_context);
  } catch (error) {
    showError(answerTarget, error);
  } finally {
    state.isAskingAi = false;
    $("askAiBtn").disabled = false;
    $("askAiBtn").textContent = "Ask AI";
  }
}

async function reflectAiSession() {
  const target = $("aiReflectionOutput");
  if (!state.conversationId) {
    target.textContent = "Ask the AI tutor first, then reflect on that session.";
    return;
  }
  try {
    const result = await api(`/ai/conversations/${state.conversationId}/reflect`, {
      method: "POST",
      body: JSON.stringify({ target_language: $("reflectionLanguage").value }),
    });
    target.textContent = [
      `AI reflection: ${result.reflection_id}`,
      "",
      result.translated_summary,
      "",
      `Weaknesses: ${result.weaknesses.join(", ")}`,
      `AI instructions: ${result.future_ai_instructions.join(" ")}`,
      `Mode: ${result.is_mock ? "mock Gemini reflection" : "Gemini reflection"}`,
    ].join("\n");
    await loadRecommendations();
  } catch (error) {
    showError(target, error);
  }
}

async function loadRecommendations() {
  try {
    const recs = await api(`/students/${state.studentId}/recommendations`);
    renderRecommendations(recs);
  } catch (error) {
    showError($("recommendationsList"), error);
  }
}

async function resetDemo() {
  await api("/demo/seed", { method: "POST", body: JSON.stringify({}) });
  await loadDemoIds();
  await Promise.all([searchSemantic(), searchNotes(), searchBooks(), searchTutors(), loadRecommendations()]);
}

async function runMainFlow() {
  await searchSemantic();
  await searchNotes();
  await searchBooks();
  await searchTutors();
  await loadRecommendations();
  setSection("notes");
}

function setDefaultBookingTime() {
  const date = new Date(Date.now() + 60 * 60 * 1000);
  date.setMinutes(0, 0, 0);
  $("bookingTime").value = date.toISOString().slice(0, 16);
}

function bindEvents() {
  document.querySelectorAll(".nav-tabs button").forEach((button) => {
    button.addEventListener("click", () => setSection(button.dataset.section));
  });
  $("semanticSearchBtn").addEventListener("click", searchSemantic);
  $("runMainFlowBtn").addEventListener("click", runMainFlow);
  $("noteSearchBtn").addEventListener("click", searchNotes);
  $("bookSearchBtn").addEventListener("click", searchBooks);
  $("tutorSearchBtn").addEventListener("click", searchTutors);
  $("joinRoomBtn").addEventListener("click", joinRoom);
  $("reflectBtn").addEventListener("click", reflectSession);
  $("askAiBtn").addEventListener("click", askAi);
  $("reflectAiBtn").addEventListener("click", reflectAiSession);
  $("startLectureBtn").addEventListener("click", startAiLecture);
  $("refreshRecsBtn").addEventListener("click", loadRecommendations);
  $("resetDemoBtn").addEventListener("click", resetDemo);

  document.addEventListener("click", async (event) => {
    const buyButton = event.target.closest("[data-buy-note]");
    if (buyButton) {
      await purchaseNote(buyButton.dataset.buyNote);
    }
    const bookButton = event.target.closest("[data-book-tutor]");
    if (bookButton) {
      await bookTutor(bookButton.dataset.bookTutor);
    }
    const addBookButton = event.target.closest("[data-add-book]");
    if (addBookButton) {
      await addBook(addBookButton.dataset.addBook);
    }
  });
}

async function init() {
  bindEvents();
  setDefaultBookingTime();
  await loadHealth();
  await loadDemoIds();
  const completed = sessionStorage.getItem("tutorloopLectureComplete");
  if (completed) {
    const payload = JSON.parse(completed);
    state.conversationId = payload.conversation_id;
    $("aiReflectionOutput").textContent = `Lecture saved (${payload.lecture_id}). Click Reflect session to update AI memory.`;
    sessionStorage.removeItem("tutorloopLectureComplete");
    setSection("ai");
  }
  await Promise.all([searchSemantic(), searchNotes(), searchBooks(), searchTutors(), loadRecommendations()]);
}

init().catch((error) => {
  document.body.insertAdjacentHTML("afterbegin", `<div class="output">Startup error: ${escapeHtml(error.message)}</div>`);
});

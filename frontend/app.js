const state = {
  studentId: "student-demo-maya",
  tutorId: "tutor-demo-elena",
  bookingId: "booking-demo-derivatives",
  sessionId: "session-demo-derivatives",
  selectedSlot: null,
  conversationId: null,
  isAskingAi: false,
  notes: [],
  books: [],
  tutors: [],
};

const sectionTitles = {
  home: "Learning Loop",
  notes: "Store",
  library: "My Library",
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

function formatTimeRange(startsAt, endsAt) {
  const start = new Date(startsAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const end = new Date(endsAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return `${start}-${end}`;
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

function renderLibrary(library) {
  const notes = library.notes || [];
  const books = library.books || [];

  $("libraryNotes").innerHTML = notes.length
    ? notes
        .map(
          (note) => `
      <article class="data-card">
        <strong>${escapeHtml(note.title)}</strong>
        <p>${escapeHtml(note.description)}</p>
        <div class="meta-row">
          ${note.subject ? pill(note.subject, "note") : ""}
          ${pill(`$${Number(note.price || 0).toFixed(2)}`, "note")}
        </div>
        <p>${escapeHtml((note.content || "").slice(0, 260))}${(note.content || "").length > 260 ? "..." : ""}</p>
      </article>
    `,
        )
        .join("")
    : $("emptyTemplate").innerHTML;

  $("libraryBooks").innerHTML = books.length
    ? books
        .map(
          (book) => `
      <article class="data-card">
        <strong>${escapeHtml(book.title)}</strong>
        <p>${escapeHtml(book.description)}</p>
        <div class="meta-row">
          ${book.subject ? pill(book.subject, "book") : ""}
          ${book.author ? pill(book.author, "tutor") : ""}
        </div>
        <p>${escapeHtml(book.preview || "No preview available yet.")}</p>
      </article>
    `,
        )
        .join("")
    : $("emptyTemplate").innerHTML;
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
    const query = encodeURIComponent($("storeQuery").value);
    state.notes = await api(`/notes/search?q=${query}`);
    renderNotes(state.notes);
  } catch (error) {
    showError($("notesResults"), error);
  }
}

async function searchTutors() {
  try {
    const query = encodeURIComponent($("tutorQuery").value);
    state.tutors = await api(`/tutors/search?q=${query}`);
    renderTutors(state.tutors);
  } catch (error) {
    showError($("tutorResults"), error);
  }
}

async function searchBooks() {
  try {
    const query = encodeURIComponent($("storeQuery").value);
    state.books = await api(`/books/search?q=${query}`);
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
  await loadLibrary();
  await loadRecommendations();
  alert(result.message);
}

async function purchaseNote(noteId) {
  const result = await api(`/notes/${noteId}/purchase`, {
    method: "POST",
    body: JSON.stringify({ student_id: state.studentId }),
  });
  await loadLibrary();
  await loadRecommendations();
  alert(result.message);
}

function renderAvailabilityCalendar(slots) {
  const target = $("availabilityCalendar");
  if (!state.tutorId) {
    target.innerHTML = `<div class="empty-state">Choose a tutor first to view their calendar.</div>`;
    return;
  }
  if (!slots.length) {
    target.innerHTML = `<div class="empty-state">No upcoming slots found for this tutor.</div>`;
    return;
  }
  const grouped = slots.reduce((acc, slot) => {
    const dateKey = new Date(slot.starts_at).toLocaleDateString();
    acc[dateKey] = acc[dateKey] || [];
    acc[dateKey].push(slot);
    return acc;
  }, {});
  target.innerHTML = Object.entries(grouped)
    .map(
      ([dateKey, daySlots]) => `
      <article class="calendar-day">
        <strong>${escapeHtml(dateKey)}</strong>
        <p>${daySlots.filter((slot) => slot.status === "available").length} available slots</p>
        <div class="slot-row">
          ${
            daySlots.filter((slot) => slot.status === "available").length
              ? daySlots
                  .filter((slot) => slot.status === "available")
                  .map((slot) => {
                    const timeRange = formatTimeRange(slot.starts_at, slot.ends_at);
                    const isSelected = state.selectedSlot && state.selectedSlot._id === slot._id;
                    return `<button class="slot-btn available ${isSelected ? "selected" : ""}" data-slot-id="${escapeHtml(slot._id)}">${escapeHtml(timeRange)}</button>`;
                  })
                  .join("")
              : `<span class="pill blocked">No available slots this day</span>`
          }
        </div>
      </article>
    `,
    )
    .join("");
}

async function loadTutorAvailability() {
  const target = $("bookingResult");
  if (!state.tutorId) {
    target.textContent = "Pick a tutor card first.";
    return;
  }
  try {
    const slots = await api(`/tutors/${state.tutorId}/availability/calendar?days=14`);
    state.currentSlots = slots;
    renderAvailabilityCalendar(slots);
  } catch (error) {
    showError(target, error);
  }
}

async function confirmBooking() {
  if (!state.tutorId || !state.selectedSlot) {
    $("bookingResult").textContent = "Select an available slot in the calendar.";
    return;
  }
  const slot = state.selectedSlot;
  const startsAt = new Date(slot.starts_at).toISOString();
  const booking = await api("/bookings", {
    method: "POST",
    body: JSON.stringify({
      tutor_id: state.tutorId,
      student_id: state.studentId,
      subject: slot.subject || "General",
      starts_at: startsAt,
      duration_minutes: 30,
    }),
  });
  state.bookingId = booking.id || booking._id;
  state.sessionId = booking.session_id;
  $("bookingResult").textContent = `Booked 30 minutes of ${booking.subject} at ${new Date(booking.starts_at).toLocaleString()} with room ${booking.room_id}. Session ${booking.session_id}.`;
  await loadTutorAvailability();
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
    const lecturePrompt = $("lecturePrompt").value.trim() || "Calculus: derivatives and tangent slope intuition";
    let subject = "Calculus";
    let topic = lecturePrompt;
    if (lecturePrompt.includes(":")) {
      const [left, ...rest] = lecturePrompt.split(":");
      if (left.trim()) subject = left.trim();
      if (rest.join(":").trim()) topic = rest.join(":").trim();
    }
    const result = await api("/ai/lecture/start", {
      method: "POST",
      body: JSON.stringify({
        student_id: state.studentId,
        subject,
        topic,
        language: "English",
      }),
    });
    sessionStorage.setItem(
      "tutorloopLecture",
      JSON.stringify({
        lecture_id: result.lecture_id,
        student_id: state.studentId,
        subject,
        topic,
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

async function loadLibrary() {
  try {
    const library = await api(`/students/${state.studentId}/library`);
    renderLibrary(library);
  } catch (error) {
    showError($("libraryNotes"), error);
    showError($("libraryBooks"), error);
  }
}

async function resetDemo() {
  await api("/demo/seed", { method: "POST", body: JSON.stringify({}) });
  await loadDemoIds();
  state.selectedSlot = null;
  await Promise.all([searchSemantic(), searchNotes(), searchBooks(), searchTutors(), loadRecommendations(), loadLibrary()]);
  renderAvailabilityCalendar([]);
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
  return;
}

function bindEvents() {
  document.querySelectorAll(".nav-tabs button").forEach((button) => {
    button.addEventListener("click", () => setSection(button.dataset.section));
  });
  $("semanticSearchBtn").addEventListener("click", searchSemantic);
  $("runMainFlowBtn").addEventListener("click", runMainFlow);
  $("storeSearchBtn").addEventListener("click", async () => {
    await Promise.all([searchNotes(), searchBooks()]);
  });
  $("tutorSearchBtn").addEventListener("click", searchTutors);
  $("refreshAvailabilityBtn").addEventListener("click", loadTutorAvailability);
  $("confirmBookingBtn").addEventListener("click", confirmBooking);
  $("joinRoomBtn").addEventListener("click", joinRoom);
  $("reflectBtn").addEventListener("click", reflectSession);
  $("askAiBtn").addEventListener("click", askAi);
  $("reflectAiBtn").addEventListener("click", reflectAiSession);
  $("startLectureBtn").addEventListener("click", startAiLecture);
  $("refreshRecsBtn").addEventListener("click", loadRecommendations);
  $("refreshLibraryBtn").addEventListener("click", loadLibrary);
  $("resetDemoBtn").addEventListener("click", resetDemo);

  document.addEventListener("click", async (event) => {
    const buyButton = event.target.closest("[data-buy-note]");
    if (buyButton) {
      await purchaseNote(buyButton.dataset.buyNote);
    }
    const bookButton = event.target.closest("[data-book-tutor]");
    if (bookButton) {
      const tutorId = bookButton.dataset.bookTutor;
      state.tutorId = tutorId;
      state.selectedSlot = null;
      setSection("booking");
      $("confirmBookingBtn").disabled = true;
      $("bookingResult").textContent = "Tutor selected. Pick an available slot from the calendar.";
      await loadTutorAvailability();
      $("availabilityCalendar").scrollIntoView({ behavior: "smooth", block: "start" });
    }
    const slotButton = event.target.closest("[data-slot-id]");
    if (slotButton) {
      const slot = (state.currentSlots || []).find((item) => item._id === slotButton.dataset.slotId);
      if (!slot || slot.status !== "available") return;
      state.selectedSlot = slot;
      $("confirmBookingBtn").disabled = false;
      $("bookingResult").textContent = `Selected ${new Date(slot.starts_at).toLocaleString()} (${slot.subject || "General"}). Click Confirm selected slot.`;
      renderAvailabilityCalendar(state.currentSlots || []);
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
  const params = new URLSearchParams(window.location.search);
  const initialSection = params.get("section");
  const initialTutorId = params.get("tutor_id");
  if (initialSection) {
    setSection(initialSection);
  }
  const completed = sessionStorage.getItem("tutorloopLectureComplete");
  if (completed) {
    const payload = JSON.parse(completed);
    state.conversationId = payload.conversation_id;
    $("aiReflectionOutput").textContent = `Lecture saved (${payload.lecture_id}). Click Reflect session to update AI memory.`;
    sessionStorage.removeItem("tutorloopLectureComplete");
    setSection("ai");
  }
  await Promise.all([searchSemantic(), searchNotes(), searchBooks(), searchTutors(), loadRecommendations(), loadLibrary()]);
  if (initialTutorId) {
    state.tutorId = initialTutorId;
    state.selectedSlot = null;
    $("confirmBookingBtn").disabled = true;
    $("bookingResult").textContent = "Tutor selected from link. Choose an available slot below.";
    await loadTutorAvailability();
  } else {
    renderAvailabilityCalendar([]);
  }
}

init().catch((error) => {
  document.body.insertAdjacentHTML("afterbegin", `<div class="output">Startup error: ${escapeHtml(error.message)}</div>`);
});

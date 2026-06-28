// Run in MongoDB Atlas or mongosh after connecting to the tutorloop database.
// Atlas Vector Search indexes can also be created from the Atlas UI.
//
// Each collection gets its OWN distinct vector index (distinct name + only the
// filter fields that collection actually uses) rather than one shared index.

const NUM_DIMENSIONS = 768;

// collection -> { name, filters }
const VECTOR_INDEXES = {
  notes: { name: "notes_vector_index", filters: ["subject", "content_type", "price", "rating"] },
  books: { name: "books_vector_index", filters: ["subject", "content_type", "price", "rating"] },
  book_chunks: { name: "book_chunks_vector_index", filters: ["subject", "content_type", "book_id"] },
  tutors: { name: "tutors_vector_index", filters: ["subjects", "content_type", "hourly_rate", "rating"] },
  transcripts: { name: "transcripts_vector_index", filters: ["subject"] },
  ai_reflections: { name: "ai_reflections_vector_index", filters: ["subject"] },
  ai_conversations: { name: "ai_conversations_vector_index", filters: ["subject"] },
};

for (const [collectionName, config] of Object.entries(VECTOR_INDEXES)) {
  const definition = {
    fields: [
      { type: "vector", path: "embedding", numDimensions: NUM_DIMENSIONS, similarity: "cosine" },
      ...config.filters.map((path) => ({ type: "filter", path })),
    ],
  };
  db.getCollection(collectionName).createSearchIndex({
    name: config.name,
    type: "vectorSearch",
    definition,
  });
  print(`${collectionName}: created ${config.name} (filters: ${config.filters.join(", ")})`);
}

db.users.createIndex({ email: 1 }, { unique: true });
db.bookings.createIndex({ student_id: 1, starts_at: -1 });
db.bookings.createIndex({ tutor_id: 1, starts_at: -1 });
db.ai_conversations.createIndex({ student_id: 1, created_at: -1 });
db.recommendations.createIndex({ student_id: 1, score: -1 });

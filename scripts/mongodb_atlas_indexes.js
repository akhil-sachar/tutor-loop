// Run in MongoDB Atlas or mongosh after connecting to the tutorloop database.
// Atlas Vector Search indexes can also be created from the Atlas UI.

const vectorIndex = {
  name: "tutorloop_vector_index",
  type: "vectorSearch",
  definition: {
    fields: [
      {
        type: "vector",
        path: "embedding",
        numDimensions: 768,
        similarity: "cosine",
      },
      { type: "filter", path: "subject" },
      { type: "filter", path: "subjects" },
      { type: "filter", path: "content_type" },
      { type: "filter", path: "price" },
      { type: "filter", path: "hourly_rate" },
      { type: "filter", path: "rating" },
    ],
  },
};

for (const collectionName of ["notes", "tutors", "transcripts", "ai_reflections", "books", "book_chunks", "ai_conversations"]) {
  db.getCollection(collectionName).createSearchIndex(vectorIndex);
}

db.users.createIndex({ email: 1 }, { unique: true });
db.bookings.createIndex({ student_id: 1, starts_at: -1 });
db.bookings.createIndex({ tutor_id: 1, starts_at: -1 });
db.ai_conversations.createIndex({ student_id: 1, created_at: -1 });
db.recommendations.createIndex({ student_id: 1, score: -1 });

# Import TutorLoop JSON data into MongoDB Atlas using mongoimport.
#
# Prerequisites:
#   1. python scripts/generate_mongodb_data.py
#   2. MongoDB Database Tools installed (mongoimport)
#
# Usage:
#   $env:MONGODB_URI = "mongodb+srv://user:pass@cluster.mongodb.net/tutorloop"
#   .\scripts\import_mongodb_data.ps1

param(
    [string]$MongoUri = $env:MONGODB_URI,
    [string]$DataDir = "$PSScriptRoot/mongodb_data",
    [switch]$SkipDrop
)

$ErrorActionPreference = "Stop"

if (-not $MongoUri) {
    Write-Error "Set MONGODB_URI or pass -MongoUri"
}

$collections = @(
    "users", "tutors", "notes", "books", "book_chunks", "purchases",
    "bookings", "sessions", "transcripts", "ai_conversations",
    "ai_reflections", "student_learning_profiles", "recommendations", "reviews"
)

if (-not (Get-Command mongoimport -ErrorAction SilentlyContinue)) {
    Write-Error "mongoimport not found. Install MongoDB Database Tools: https://www.mongodb.com/try/download/database-tools"
}

if (-not $SkipDrop) {
    Write-Host "Dropping existing collections via mongosh..."
    if (-not (Get-Command mongosh -ErrorAction SilentlyContinue)) {
        Write-Warning "mongosh not found; skipping drop step. Use --upload --reset with generate_mongodb_data.py instead."
    } else {
        mongosh $MongoUri --eval "db.getCollectionNames().forEach(function(name){ if (['users','tutors','notes','books','book_chunks','purchases','bookings','sessions','transcripts','ai_conversations','ai_reflections','student_learning_profiles','recommendations','reviews'].includes(name)) db.getCollection(name).drop(); })"
    }
}

foreach ($collection in $collections) {
    $file = Join-Path $DataDir "$collection.json"
    if (-not (Test-Path $file)) {
        Write-Warning "Missing $file"
        continue
    }
    Write-Host "Importing $collection..."
    mongoimport --uri $MongoUri --collection $collection --file $file --jsonArray --drop
}

Write-Host "Creating vector search indexes..."
mongosh $MongoUri --file "$PSScriptRoot/mongodb_atlas_indexes.js"
Write-Host "Done."

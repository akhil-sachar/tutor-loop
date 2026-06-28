"""Seed a diverse, multi-subject catalog of NOTES into MongoDB.

Adds notes across Math, Algebra, Linear Algebra, Statistics, Probability,
Chemistry, Organic Chemistry, Physics, Quantum, Biology, Genetics, Data Science,
Machine Learning, Deep Learning, LLM/NLP, Computer Science, and Economics so that
Store search returns clearly different results per subject.

Books are intentionally NOT seeded here: the AI tutor's book library comes only
from the content/ folder (ingested by BookService). Any non-content books are
pruned on startup.

Idempotent: upserts notes by _id. Generates real Gemini embeddings when
GEMINI_API_KEY is set (mock embeddings otherwise).

Usage:
    python scripts/seed_diverse_catalog.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.core.config import get_settings
from backend.app.db.mongo import AppDatabase, utc_now
from backend.app.services.gemini_service import GeminiService
from backend.app.services.vector_search import VectorSearchService

PLATFORM_TUTOR = "tutor-platform"


# (id, subject, title, price, rating, description, content)
NOTES = [
    ("note-algebra-linear-eq", "Algebra", "Linear Equations & Slope-Intercept Mastery", 6.5, 4.7,
     "Breaks down slope-intercept, point-slope, and standard form with worked conversions.\n"
     "Shows how to read slope and intercept directly off a graph or a word problem.\n"
     "Includes common sign-error traps and a quick self-check routine.",
     "A linear equation y = mx + b has slope m and y-intercept b. To graph, plot b on the y-axis, "
     "then use rise-over-run from m. Convert standard form Ax+By=C by solving for y."),
    ("note-linalg-vectors", "Linear Algebra", "Vectors, Matrices, and Transformations", 9.0, 4.8,
     "Connects matrices to linear transformations geometrically instead of rote computation.\n"
     "Covers dot products, matrix multiplication, and what determinants actually mean.\n"
     "Builds toward eigenvectors with visual intuition for scaling directions.",
     "A matrix is a linear transformation: columns show where the basis vectors land. Matrix-vector "
     "multiplication is a weighted sum of columns. The determinant measures how area/volume scales."),
    ("note-stats-hypothesis", "Statistics", "Hypothesis Testing Demystified", 8.0, 4.6,
     "Explains null vs alternative hypotheses, p-values, and significance without jargon.\n"
     "Walks through t-tests and when to use one-tailed vs two-tailed tests.\n"
     "Clarifies the difference between statistical and practical significance.",
     "A p-value is the probability of seeing data this extreme if the null hypothesis were true. "
     "Reject the null when p < alpha. A t-test compares means relative to their variability."),
    ("note-prob-distributions", "Probability", "Probability Distributions Cheat Sheet", 7.0, 4.5,
     "Summarizes binomial, Poisson, normal, and exponential distributions side by side.\n"
     "Gives the mean, variance, and a real-world example for each distribution.\n"
     "Includes a decision guide for picking the right distribution for a problem.",
     "The binomial counts successes in n trials; the Poisson models rare events over an interval; "
     "the normal is the bell curve from the Central Limit Theorem."),
    ("note-chem-stoich", "Chemistry", "Stoichiometry Step-by-Step", 7.5, 4.7,
     "Teaches the mole-ratio method for balancing reactions and computing yields.\n"
     "Covers limiting reagents, percent yield, and unit conversions with grams and moles.\n"
     "Uses a repeatable 4-step framework students can apply under exam pressure.",
     "Stoichiometry uses balanced equations to relate amounts. Convert grams to moles, apply the "
     "mole ratio from coefficients, then convert back. The limiting reagent runs out first."),
    ("note-orgchem-mechanisms", "Organic Chemistry", "Reaction Mechanisms & Arrow Pushing", 10.0, 4.6,
     "Demystifies curved-arrow notation for nucleophiles, electrophiles, and leaving groups.\n"
     "Compares SN1, SN2, E1, and E2 pathways with the factors that favor each.\n"
     "Provides a mechanism-prediction checklist for unfamiliar reactions.",
     "Curved arrows show electron movement from nucleophile to electrophile. SN2 is one concerted "
     "step with backside attack; SN1 goes through a carbocation intermediate."),
    ("note-phys-newton", "Physics", "Newton's Laws and Free-Body Diagrams", 8.0, 4.8,
     "Shows how to draw free-body diagrams and resolve forces into components.\n"
     "Connects F = ma to real scenarios like inclines, pulleys, and friction.\n"
     "Includes sign-convention tips that prevent most setup mistakes.",
     "Newton's second law: net force equals mass times acceleration. Draw every force as an arrow, "
     "split into x and y components, then solve sum(F) = ma along each axis."),
    ("note-phys-em", "Physics", "Electric Fields and Gauss's Law", 9.5, 4.5,
     "Explains electric fields, flux, and how symmetry makes Gauss's law powerful.\n"
     "Works through spheres, cylinders, and infinite planes as canonical examples.\n"
     "Links field lines to potential and the direction of force on charges.",
     "Gauss's law says the electric flux through a closed surface equals enclosed charge over "
     "epsilon-zero. Exploit symmetry to pull E outside the integral."),
    ("note-quantum-wavefunctions", "Quantum Physics", "Intro to Wavefunctions and Superposition", 11.0, 4.4,
     "Introduces the wavefunction, probability amplitudes, and the Born rule gently.\n"
     "Explains superposition and measurement collapse with the double-slit experiment.\n"
     "Sets up the language needed before tackling the Schrodinger equation.",
     "The wavefunction psi encodes probability amplitudes; |psi|^2 gives the probability density. "
     "A system can exist in a superposition of states until measured."),
    ("note-bio-cell", "Biology", "Cell Structure and Organelles", 6.0, 4.7,
     "Maps each organelle to its function with analogies that stick.\n"
     "Contrasts prokaryotic and eukaryotic cells and plant vs animal cells.\n"
     "Includes a labeled-diagram practice set for exam recall.",
     "The nucleus stores DNA; mitochondria produce ATP; ribosomes build proteins; the endoplasmic "
     "reticulum and Golgi process and ship them."),
    ("note-genetics-mendel", "Genetics", "Mendelian Genetics and Punnett Squares", 6.5, 4.6,
     "Explains dominant/recessive alleles, genotype vs phenotype, and ratios.\n"
     "Walks through monohybrid and dihybrid crosses with Punnett squares.\n"
     "Adds tips for probability-based genetics questions.",
     "Each parent contributes one allele per gene. A monohybrid Aa x Aa cross gives a 3:1 phenotype "
     "ratio and a 1:2:1 genotype ratio."),
    ("note-ds-eda", "Data Science", "Exploratory Data Analysis with Pandas", 9.0, 4.8,
     "Covers loading, cleaning, and profiling tabular data with pandas.\n"
     "Shows groupby, pivot, and visualization patterns for finding signal.\n"
     "Emphasizes handling missing values and outliers before modeling.",
     "EDA starts with df.info() and df.describe(). Use groupby to aggregate, value_counts for "
     "categoricals, and histograms/boxplots to spot skew and outliers."),
    ("note-ds-feature-eng", "Data Science", "Feature Engineering Essentials", 9.5, 4.6,
     "Explains encoding categoricals, scaling, and creating interaction features.\n"
     "Covers leakage pitfalls and why you fit transforms on training data only.\n"
     "Includes a checklist for turning raw columns into model-ready features.",
     "Feature engineering turns raw data into informative inputs: one-hot or target encoding for "
     "categoricals, standardization for scale-sensitive models, and date/text decomposition."),
    ("note-ml-bias-variance", "Machine Learning", "Bias-Variance and Model Evaluation", 9.0, 4.7,
     "Unpacks the bias-variance tradeoff and how it drives under/overfitting.\n"
     "Explains train/validation/test splits, cross-validation, and metric choice.\n"
     "Connects learning curves to concrete next steps for improving a model.",
     "High bias underfits; high variance overfits. Use cross-validation to estimate generalization, "
     "and pick metrics (accuracy, F1, ROC-AUC) that match the problem."),
    ("note-ml-gradient-descent", "Machine Learning", "Gradient Descent Intuition", 8.5, 4.8,
     "Builds intuition for gradients, learning rates, and convergence.\n"
     "Compares batch, stochastic, and mini-batch gradient descent.\n"
     "Shows how momentum and learning-rate schedules stabilize training.",
     "Gradient descent steps downhill against the gradient of the loss. Too-large learning rates "
     "diverge; too-small ones crawl. Mini-batches trade noise for speed."),
    ("note-dl-backprop", "Deep Learning", "Backpropagation Explained", 10.0, 4.7,
     "Derives backprop as the chain rule applied across network layers.\n"
     "Explains forward pass, loss, and gradient flow with a tiny worked network.\n"
     "Covers vanishing gradients and why activation choice matters.",
     "Backpropagation computes loss gradients layer by layer using the chain rule, reusing "
     "intermediate values from the forward pass to update weights efficiently."),
    ("note-llm-transformers", "LLM", "How Transformers and Attention Work", 12.0, 4.9,
     "Explains self-attention, queries/keys/values, and multi-head attention.\n"
     "Walks through positional encoding and the encoder-decoder structure.\n"
     "Connects the architecture to why LLMs scale so well.",
     "Self-attention lets each token weigh every other token via query-key dot products, producing "
     "context-aware representations. Multiple heads capture different relationships in parallel."),
    ("note-llm-rag-prompting", "LLM", "Prompt Engineering and RAG Basics", 11.0, 4.8,
     "Covers prompt structure, few-shot examples, and controlling output format.\n"
     "Introduces retrieval-augmented generation to ground models in your data.\n"
     "Explains chunking, embeddings, and vector search for RAG pipelines.",
     "RAG retrieves relevant chunks via vector search and adds them to the prompt so the LLM answers "
     "from your data. Good chunking and embeddings drive retrieval quality."),
    ("note-cs-bigo", "Computer Science", "Big-O and Algorithm Analysis", 7.5, 4.7,
     "Defines Big-O, Big-Theta, and how to reason about worst-case growth.\n"
     "Compares common complexities from O(1) to O(2^n) with examples.\n"
     "Shows how to analyze loops, recursion, and divide-and-conquer.",
     "Big-O describes how runtime grows with input size n. Nested loops are often O(n^2); binary "
     "search is O(log n); divide-and-conquer like mergesort is O(n log n)."),
    ("note-cs-data-structures", "Computer Science", "Hash Maps, Trees, and Graphs", 8.0, 4.6,
     "Compares arrays, hash maps, trees, and graphs by operation cost.\n"
     "Explains when to reach for each structure in interviews and projects.\n"
     "Covers BFS/DFS traversal and balanced-tree basics.",
     "Hash maps give average O(1) lookup; balanced trees give O(log n) ordered operations; graphs "
     "model relationships and are traversed with BFS or DFS."),
    ("note-econ-supply-demand", "Economics", "Supply, Demand, and Elasticity", 6.5, 4.5,
     "Explains market equilibrium and how shifts in supply or demand move price.\n"
     "Introduces price elasticity and what makes goods elastic or inelastic.\n"
     "Uses graphs to connect consumer behavior to revenue decisions.",
     "Equilibrium is where supply meets demand. A demand shift changes price and quantity together; "
     "elasticity measures how responsive quantity is to a price change."),
    ("note-calc-integration", "Calculus", "Integration Techniques Toolkit", 9.0, 4.7,
     "Organizes u-substitution, integration by parts, and partial fractions.\n"
     "Gives a decision tree for choosing the right technique fast.\n"
     "Includes definite-integral and area-under-curve applications.",
     "Integration reverses differentiation. Use u-substitution for composite functions, parts for "
     "products (LIATE), and partial fractions for rational functions."),
]


# NOTE: Books are no longer seeded here (content/ folder is the only book source).
_UNUSED_BOOKS = [
    ("book-linalg-companion", "Linear Algebra", "Linear Algebra: A Geometric Companion", "A. Rivera", 0.0, 4.8,
     "A geometry-first companion to linear algebra emphasizing transformations.\n"
     "Connects matrices, determinants, and eigenvectors to visual intuition.\n"
     "Ideal alongside any standard linear algebra course.",
     ["Vectors can be added tip-to-tail and scaled; a basis is a minimal set whose combinations span the space.",
      "A matrix encodes a linear transformation. Its columns are the images of the basis vectors.",
      "Eigenvectors keep their direction under a transformation; the eigenvalue is the scaling factor."]),
    ("book-practical-stats", "Statistics", "Practical Statistics for Analysts", "M. Chen", 0.0, 4.7,
     "Bridges classical statistics and modern data analysis.\n"
     "Covers estimation, testing, regression, and resampling methods.\n"
     "Focused on intuition and practical pitfalls over heavy proofs.",
     ["Sampling distributions describe how a statistic varies across samples; the standard error quantifies that spread.",
      "Confidence intervals express uncertainty; a 95% interval would contain the parameter 95% of the time across repeated samples.",
      "Linear regression fits a line minimizing squared residuals; check assumptions with residual plots."]),
    ("book-general-chem", "Chemistry", "General Chemistry Principles", "L. Okafor", 0.0, 4.6,
     "A clear foundation in atomic structure, bonding, and reactions.\n"
     "Builds from the periodic table to thermodynamics and equilibrium.\n"
     "Includes worked examples and conceptual checkpoints.",
     ["Atoms bond to reach stable electron configurations, forming ionic or covalent bonds.",
      "Reaction rates depend on concentration, temperature, and catalysts via collision theory.",
      "At equilibrium, forward and reverse reaction rates are equal and concentrations stay constant."]),
    ("book-university-physics", "Physics", "University Physics Essentials", "R. Datta", 0.0, 4.7,
     "Core mechanics, electromagnetism, and waves for first-year physics.\n"
     "Pairs concepts with problem-solving strategies and diagrams.\n"
     "Designed to complement calculus-based physics courses.",
     ["Kinematics relates position, velocity, and acceleration; calculus connects them as derivatives and integrals.",
      "Energy is conserved: work done by net force equals the change in kinetic energy.",
      "Electric and magnetic fields are unified by Maxwell's equations, which predict electromagnetic waves."]),
    ("book-molecular-bio", "Biology", "Molecular Biology of the Cell: Primer", "S. Whitman", 0.0, 4.6,
     "An accessible primer on cellular and molecular biology.\n"
     "Covers DNA, transcription, translation, and the cell cycle.\n"
     "Connects molecular detail to whole-cell behavior.",
     ["DNA stores genetic information in base pairs; replication copies it before cell division.",
      "Transcription makes mRNA from DNA; translation builds proteins from mRNA at ribosomes.",
      "The cell cycle is tightly regulated by checkpoints to prevent errors and uncontrolled growth."]),
    ("book-pyds-handbook", "Data Science", "Python Data Science Handbook (Study Notes)", "K. Sato", 0.0, 4.8,
     "Condensed notes on the Python data science stack.\n"
     "Covers NumPy, pandas, visualization, and an intro to scikit-learn.\n"
     "Practical, example-driven, and project-oriented.",
     ["NumPy arrays enable fast vectorized computation; broadcasting applies operations across shapes.",
      "pandas DataFrames handle labeled tabular data with powerful groupby and merge operations.",
      "scikit-learn offers a consistent fit/predict API across many models and preprocessing tools."]),
    ("book-hands-on-ml", "Machine Learning", "Hands-On Machine Learning Guide", "D. Moreau", 0.0, 4.9,
     "A practical path from classical ML to model deployment.\n"
     "Covers pipelines, evaluation, regularization, and tuning.\n"
     "Balances theory with reproducible, code-first workflows.",
     ["A typical ML workflow: split data, build a preprocessing pipeline, train, validate, and tune hyperparameters.",
      "Regularization (L1/L2) penalizes complexity to reduce overfitting and improve generalization.",
      "Ensembles like random forests and gradient boosting combine weak learners for stronger predictions."]),
    ("book-deep-learning", "Deep Learning", "Deep Learning Foundations", "P. Andersson", 0.0, 4.7,
     "Foundations of neural networks and modern architectures.\n"
     "Covers backpropagation, CNNs, RNNs, and regularization.\n"
     "Prepares readers for transformer-based models.",
     ["Neural networks stack linear layers with nonlinear activations to learn complex functions.",
      "Convolutional networks share weights across space, making them efficient for images.",
      "Dropout and batch normalization stabilize and regularize deep network training."]),
    ("book-nlp-transformers", "LLM", "Natural Language Processing with Transformers", "J. Park", 0.0, 4.9,
     "A modern guide to NLP built around transformer models.\n"
     "Covers tokenization, attention, fine-tuning, and evaluation.\n"
     "Connects pretrained models to real downstream tasks.",
     ["Tokenization splits text into subword units that map to embedding vectors.",
      "The transformer's self-attention computes context-aware representations without recurrence.",
      "Fine-tuning adapts a pretrained model to a specific task with relatively little data."]),
    ("book-llm-apps-rag", "LLM", "Building LLM Applications with RAG", "T. Nakamura", 0.0, 4.8,
     "A practical playbook for production LLM apps.\n"
     "Covers retrieval-augmented generation, embeddings, and vector search.\n"
     "Addresses evaluation, guardrails, and chunking strategies.",
     ["RAG grounds an LLM by retrieving relevant documents from a vector database and injecting them into the prompt.",
      "Embedding quality and chunking strategy strongly affect retrieval relevance.",
      "Evaluation should measure both retrieval accuracy and final answer faithfulness to sources."]),
    ("book-algorithms-companion", "Computer Science", "Introduction to Algorithms (Companion)", "G. Alvarez", 0.0, 4.7,
     "A study companion for core algorithms and data structures.\n"
     "Covers sorting, searching, graphs, and dynamic programming.\n"
     "Emphasizes complexity analysis and design patterns.",
     ["Divide-and-conquer splits a problem into subproblems, solves them, and combines results, as in mergesort.",
      "Dynamic programming stores subproblem solutions to avoid recomputation in overlapping subproblems.",
      "Graph algorithms like Dijkstra find shortest paths using a priority queue."]),
    ("book-microeconomics", "Economics", "Principles of Microeconomics", "H. Bauer", 0.0, 4.5,
     "An introduction to how individuals and firms make decisions.\n"
     "Covers supply, demand, elasticity, and market structures.\n"
     "Uses graphs and everyday examples to build intuition.",
     ["Markets allocate resources through the interaction of supply and demand to reach equilibrium.",
      "Elasticity measures responsiveness of quantity to changes in price or income.",
      "Market structures range from perfect competition to monopoly, affecting price and output."]),
]


async def main() -> None:
    settings = get_settings()
    if not settings.mongodb_uri:
        raise SystemExit("MONGODB_URI is not set. This script seeds Atlas directly.")

    db = AppDatabase(settings)
    await db.connect()
    if not db.is_mongo:
        raise SystemExit(f"Could not connect to MongoDB: {db.connection_error}")

    gemini = GeminiService(settings)
    vs = VectorSearchService(db, gemini, settings)
    print(f"Connected to {settings.mongodb_db_name}. gemini.is_mock={gemini.is_mock}")

    note_count = 0
    for note_id, subject, title, price, rating, description, content in NOTES:
        doc = {
            "_id": note_id,
            "tutor_id": PLATFORM_TUTOR,
            "title": title,
            "subject": subject,
            "description": description,
            "price": float(price),
            "content": content,
            "rating": float(rating),
            "purchases_count": 0,
            "content_type": "note",
            "created_at": utc_now(),
        }
        doc["embedding"] = await vs.embed_document(doc, ["title", "subject", "description", "content"])
        await db.update_one("notes", {"_id": note_id}, {"$set": doc}, upsert=True)
        note_count += 1
        print(f"  note: {subject:18} {title}")

    print(f"\nDone. Upserted {note_count} notes. (Books come only from the content/ folder.)")
    await db.close()


if __name__ == "__main__":
    asyncio.run(main())

"""
ml_engine.py – Machine Learning Backend for EduPath India
=========================================================
Provides three core ML components:
  1. SemanticSearchEngine  – TF-IDF + cosine similarity for natural language search
  2. UniversityMatchModel  – Gradient Boosting classifier for profile-based matching
  3. RAGRetriever          – Embedding-based retrieval for chatbot context injection

All models are trained/fitted lazily on first use and cached in memory.
"""

import re
import json
import random
import hashlib
import numpy as np
from typing import List, Dict, Tuple, Optional, Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from sklearn.pipeline import Pipeline

# ─────────────────────────────────────────────────────────────────────────────
#  UTILITY: Build searchable text from data records
# ─────────────────────────────────────────────────────────────────────────────

def _build_uni_text(uni: dict) -> str:
    """Create a rich text representation of a university for search/embedding."""
    parts = [
        uni.get("name", ""),
        uni.get("city", ""),
        uni.get("country", ""),
        uni.get("domain", ""),
        " ".join(uni.get("degrees", [])),
        " ".join(uni.get("required_exams", [])),
        " ".join(uni.get("highlights", [])),
        uni.get("scholarships_available", ""),
        f"fees {uni.get('fees_inr', '')} INR {uni.get('fees_usd', '')} USD",
        f"rank {uni.get('rank', '')}",
        f"rating {uni.get('rating', '')}",
        f"admission {uni.get('admission_status', '')}",
        f"deadline {uni.get('deadline', '')}",
    ]
    return " ".join(parts).lower()


def _build_exam_text(exam: dict) -> str:
    """Create text representation of an exam."""
    parts = [
        exam.get("name", ""),
        exam.get("full_name", ""),
        exam.get("domain", ""),
        exam.get("body", ""),
        exam.get("mode", ""),
        " ".join(exam.get("accepted_by", exam.get("accepted_in", []))),
        exam.get("score_info", ""),
        f"fee {exam.get('fee', exam.get('fee_inr', ''))}",
        f"validity {exam.get('validity', '')}",
    ]
    return " ".join(parts).lower()


def _build_scholarship_text(schol: dict) -> str:
    """Create text representation of a scholarship."""
    parts = [
        schol.get("name", ""),
        schol.get("body", ""),
        schol.get("type", ""),
        schol.get("description", ""),
        schol.get("eligibility", ""),
        " ".join(schol.get("countries", [])),
        " ".join(schol.get("levels", [])),
        " ".join(schol.get("covers", [])),
        schol.get("amount_inr", ""),
        f"deadline {schol.get('deadline', '')}",
        "renewable" if schol.get("renewable") else "one-time",
    ]
    return " ".join(parts).lower()


def _parse_fee_lakhs(fee_str: str) -> float:
    """Parse fee string to a float in lakhs."""
    m = re.search(r"[\d.]+", str(fee_str).replace(",", ""))
    return float(m.group()) if m else 0.0


# ─────────────────────────────────────────────────────────────────────────────
#  1. SEMANTIC SEARCH ENGINE  (TF-IDF + Cosine Similarity)
# ─────────────────────────────────────────────────────────────────────────────

class SemanticSearchEngine:
    """
    TF-IDF based semantic search over universities, exams, and scholarships.
    Replaces simple substring matching with cosine-similarity ranked results.
    """

    def __init__(self):
        self._vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),       # unigrams + bigrams + trigrams
            stop_words="english",
            sublinear_tf=True,        # applies log normalization to TF
            min_df=1,
            max_df=0.95,
        )
        self._corpus_texts: List[str] = []
        self._corpus_items: List[dict] = []
        self._corpus_types: List[str] = []
        self._tfidf_matrix = None
        self._is_fitted = False

    def fit(self, universities: List[dict], exams: List[dict] = None,
            scholarships: List[dict] = None):
        """Build the TF-IDF index over all data."""
        self._corpus_texts = []
        self._corpus_items = []
        self._corpus_types = []

        for uni in universities:
            self._corpus_texts.append(_build_uni_text(uni))
            self._corpus_items.append(uni)
            self._corpus_types.append("university")

        if exams:
            for exam in exams:
                self._corpus_texts.append(_build_exam_text(exam))
                self._corpus_items.append(exam)
                self._corpus_types.append("exam")

        if scholarships:
            for schol in scholarships:
                self._corpus_texts.append(_build_scholarship_text(schol))
                self._corpus_items.append(schol)
                self._corpus_types.append("scholarship")

        if self._corpus_texts:
            self._tfidf_matrix = self._vectorizer.fit_transform(self._corpus_texts)
            self._is_fitted = True

    def search(self, query: str, top_k: int = 50,
               item_type: str = None) -> List[Tuple[dict, float]]:
        """
        Search the corpus with a natural language query.
        Returns: list of (item_dict, similarity_score) tuples, sorted by score desc.
        """
        if not self._is_fitted or not query.strip():
            return [(item, 1.0) for item in self._corpus_items
                    if item_type is None or self._corpus_types[self._corpus_items.index(item)] == item_type]

        query_vec = self._vectorizer.transform([query.lower()])
        similarities = cosine_similarity(query_vec, self._tfidf_matrix).flatten()

        # Create (index, score) pairs
        scored = list(enumerate(similarities))

        # Filter by type if specified
        if item_type:
            scored = [(i, s) for i, s in scored if self._corpus_types[i] == item_type]

        # Sort by similarity score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Return top_k results with score > 0
        results = []
        for idx, score in scored[:top_k]:
            if score > 0.0:
                results.append((self._corpus_items[idx], float(score)))

        return results

    def search_universities(self, query: str, universities: List[dict],
                            top_k: int = 50) -> List[Tuple[dict, float]]:
        """
        Search universities specifically. Returns matches with scores.
        Uses the pre-fitted index but filters to university type only.
        """
        if not self._is_fitted or not query.strip():
            return [(u, 1.0) for u in universities]

        query_vec = self._vectorizer.transform([query.lower()])
        similarities = cosine_similarity(query_vec, self._tfidf_matrix).flatten()

        # Map university names to their similarity scores
        uni_name_set = {u["name"] for u in universities}
        scored_unis = []
        for i, score in enumerate(similarities):
            if (self._corpus_types[i] == "university" and
                    self._corpus_items[i]["name"] in uni_name_set and
                    score > 0.0):
                scored_unis.append((self._corpus_items[i], float(score)))

        scored_unis.sort(key=lambda x: x[1], reverse=True)
        return scored_unis[:top_k]


# ─────────────────────────────────────────────────────────────────────────────
#  2. UNIVERSITY MATCH MODEL  (Gradient Boosting Regressor)
# ─────────────────────────────────────────────────────────────────────────────

# Domain and degree encodings for feature engineering
DOMAIN_LIST = [
    "Engineering", "Data Science & AI", "Management", "Medical & Health",
    "Law", "Arts & Humanities", "Sciences", "Design & Architecture",
    "Computer Science", "Finance & Accounting", "Education", "Agriculture",
    "Pharmacy & Biotech", "Media & Communication", "Social Sciences",
    "Environmental Studies", "Hospitality & Tourism", "Fashion & Textile",
    "Psychology", "Public Policy",
]

DEGREE_GROUPS = {
    "Bachelors": 0, "Masters": 1, "MBA": 2, "PhD": 3,
    "Diploma": 4, "Certificate": 5,
}


def _degree_to_group(degree_str: str) -> str:
    """Map a full degree name to its group."""
    degree_lower = degree_str.lower()
    if "phd" in degree_lower or "m.phil" in degree_lower or "dba" in degree_lower:
        return "PhD"
    if "mba" in degree_lower or "pgdm" in degree_lower or "executive" in degree_lower:
        return "MBA"
    if "master" in degree_lower or "m.tech" in degree_lower or "m.sc" in degree_lower or \
       "mca" in degree_lower or "m.com" in degree_lower or "llm" in degree_lower or \
       "m.arch" in degree_lower or "mph" in degree_lower or "mfa" in degree_lower or \
       "msw" in degree_lower or "md" in degree_lower or "mds" in degree_lower or \
       "m.pharm" in degree_lower:
        return "Masters"
    if "bachelor" in degree_lower or "b.tech" in degree_lower or "b.sc" in degree_lower or \
       "bba" in degree_lower or "b.com" in degree_lower or "mbbs" in degree_lower or \
       "llb" in degree_lower or "b.arch" in degree_lower or "bfa" in degree_lower or \
       "b.pharm" in degree_lower or "integrated" in degree_lower:
        return "Bachelors"
    if "diploma" in degree_lower:
        return "Diploma"
    if "certificate" in degree_lower:
        return "Certificate"
    return "Masters"  # default


class UniversityMatchModel:
    """
    ML model that predicts how well a university matches a student profile.
    Uses GradientBoostingRegressor trained on synthetic data.
    """

    def __init__(self):
        self._model = GradientBoostingRegressor(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.1,
            min_samples_split=5,
            min_samples_leaf=3,
            subsample=0.8,
            random_state=42,
        )
        self._scaler = MinMaxScaler()
        self._is_trained = False
        self._domain_encoder = {}
        for i, d in enumerate(DOMAIN_LIST):
            self._domain_encoder[d.lower()] = i

    def _extract_features(self, uni: dict, profile: dict) -> np.ndarray:
        """Extract feature vector from a (university, profile) pair."""
        features = []

        # 1. Academic score (normalized to 0-1)
        score_pct = profile.get("score_pct", 0) / 100.0
        features.append(score_pct)

        # 2. Exam scores (normalized)
        features.append(min(profile.get("gre", 0) / 340.0, 1.0))
        features.append(min(profile.get("gmat", 0) / 805.0, 1.0))
        features.append(min(profile.get("ielts", 0) / 9.0, 1.0))
        features.append(min(profile.get("toefl", 0) / 120.0, 1.0))
        features.append(min(profile.get("gate", 0) / 1000.0, 1.0))
        features.append(min(profile.get("cat", 0) / 100.0, 1.0))
        features.append(min(profile.get("sat", 0) / 1600.0, 1.0))

        # 3. Domain match (fuzzy)
        desired_domain = profile.get("desired_domain", "").lower()
        uni_domain = uni.get("domain", "").lower()
        if not desired_domain or desired_domain == "all":
            domain_match = 1.0
        elif desired_domain == uni_domain:
            domain_match = 1.0
        elif desired_domain in uni_domain or uni_domain in desired_domain:
            domain_match = 0.7
        else:
            domain_match = 0.0
        features.append(domain_match)

        # 4. Degree level match (binary)
        desired_level = profile.get("desired_level", "")
        desired_group = _degree_to_group(desired_level)
        uni_degrees = uni.get("degrees", [])
        uni_degree_groups = [_degree_to_group(d) for d in uni_degrees]
        level_match = 1.0 if desired_group in uni_degree_groups or desired_level in uni_degrees else 0.0
        features.append(level_match)

        # 5. Country/destination match
        target_dest = profile.get("target_dest", [])
        if not target_dest or "all" in [d.lower() for d in target_dest]:
            country_match = 1.0
        else:
            country_match = 1.0 if uni.get("country") in target_dest else 0.0
        features.append(country_match)
        
        # 5b. Name Hash (for unique model personality)
        name_hash = int(hashlib.md5(uni.get("name", "").encode()).hexdigest(), 16)
        features.append((name_hash % 100) / 100.0)

        # 6. Budget-to-fee ratio (higher = more affordable)
        fee_val = _parse_fee_lakhs(uni.get("fees_inr", "0"))
        budget_max = profile.get("budget_max", 80)
        budget_ratio = min((budget_max + 1) / (fee_val + 1), 5.0) / 5.0
        features.append(budget_ratio)

        # 7. University rank (normalized, lower is better)
        rank = uni.get("rank", 100)
        rank_normalized = 1.0 - min(rank / 200.0, 1.0)
        features.append(rank_normalized)

        # 8. University rating (normalized)
        rating = uni.get("rating", 3.0)
        features.append(rating / 5.0)

        # 9. Admission status (encoded)
        status = uni.get("admission_status", "Closed")
        status_score = {"Open": 1.0, "Closing Soon": 0.5, "Closed": 0.0}.get(status, 0.0)
        features.append(status_score)

        # 10. Has required exam scores (fraction of required exams user has)
        required_exams = uni.get("required_exams", [])
        exam_score_map = {
            "GRE": profile.get("gre", 0), "GMAT Focus": profile.get("gmat", 0),
            "IELTS": profile.get("ielts", 0), "TOEFL iBT": profile.get("toefl", 0),
            "GATE": profile.get("gate", 0), "CAT": profile.get("cat", 0),
            "SAT": profile.get("sat", 0), "JEE Advanced": 0, "JEE Main": 0,
            "NEET UG": 0, "NEET PG": 0, "CLAT": 0, "AILET": 0,
        }
        if required_exams:
            has_count = sum(1 for ex in required_exams if exam_score_map.get(ex, 0) > 0)
            exam_coverage = has_count / len(required_exams)
        else:
            exam_coverage = 0.5
        features.append(exam_coverage)

        # 11. Scholarship availability
        has_schol = 1.0 if uni.get("scholarships_available") else 0.0
        features.append(has_schol)

        # 12. Priority flags
        priorities = profile.get("priorities", [])
        features.append(1.0 if "High Ranking" in priorities else 0.0)
        features.append(1.0 if "Low Fees" in priorities else 0.0)
        features.append(1.0 if "Scholarships" in priorities else 0.0)
        features.append(1.0 if "Research Focus" in priorities else 0.0)

        # 13. India vs Abroad
        is_india = 1.0 if uni.get("country") == "India" else 0.0
        features.append(is_india)

        # 14. Domain encoding (numeric)
        domain_idx = self._domain_encoder.get(uni_domain, len(DOMAIN_LIST))
        features.append(domain_idx / (len(DOMAIN_LIST) + 1))
        
        # 15. Base Profile Score (Independent of university)
        # This ensures scores CHANGE when profile changes even if uni features are constant
        base_score = (score_pct * 0.5 + 
                      min(profile.get("gre", 0) / 340.0, 1.0) * 0.2 + 
                      min(profile.get("ielts", 0) / 9.0, 1.0) * 0.3)
        features.append(base_score)

        return np.array(features, dtype=np.float64)

    def _generate_training_data(self, universities: List[dict]) -> Tuple[np.ndarray, np.ndarray]:
        """Generate synthetic training data for the match model."""
        random.seed(42)
        np.random.seed(42)

        X_data = []
        y_data = []

        # Generate diverse synthetic profiles
        domains = DOMAIN_LIST
        degree_levels = [
            "Bachelors (B.Tech/B.E.)", "Masters (M.Tech/M.E.)", "Masters (M.Sc.)",
            "MBA", "PhD", "Masters (MCA)", "Masters (MA)", "Bachelors (B.Sc.)",
            "Bachelors (MBBS/BDS)", "Bachelors (LLB)", "PG Diploma",
        ]
        countries_pool = [
            ["India"], ["USA"], ["UK"], ["Canada"], ["Australia"],
            ["Germany"], ["Singapore"], ["India", "USA"],
            ["USA", "UK", "Canada"], ["India", "Germany"],
            ["USA", "UK"], ["Australia", "Canada"],
        ]
        priority_options = [
            ["High Ranking"], ["Low Fees"], ["Scholarships"],
            ["High Ranking", "Scholarships"], ["Low Fees", "Scholarships"],
            ["Research Focus"], ["High Ranking", "Research Focus"],
            ["Industry Connections"], ["Low Fees", "Research Focus"],
            [],
        ]

        for _ in range(300):
            # Random profile
            profile = {
                "score_pct": random.uniform(45, 98),
                "gre": random.choice([0, 0, 0, random.randint(260, 340)]),
                "gmat": random.choice([0, 0, 0, 0, random.randint(400, 780)]),
                "ielts": random.choice([0, 0, 0, round(random.uniform(5.0, 9.0), 1)]),
                "toefl": random.choice([0, 0, 0, random.randint(60, 120)]),
                "gate": random.choice([0, 0, 0, 0, random.randint(200, 900)]),
                "cat": random.choice([0, 0, 0, 0, round(random.uniform(50, 99.9), 1)]),
                "sat": random.choice([0, 0, 0, 0, 0, random.randint(800, 1600)]),
                "desired_domain": random.choice(domains),
                "desired_level": random.choice(degree_levels),
                "target_dest": random.choice(countries_pool),
                "budget_max": random.choice([5, 10, 20, 30, 50, 80]),
                "priorities": random.choice(priority_options),
            }

            for uni in universities:
                features = self._extract_features(uni, profile)

                # Compute expert-based label (ground truth score)
                label = self._compute_expert_label(uni, profile)

                X_data.append(features)
                y_data.append(label)

        return np.array(X_data), np.array(y_data)

    def _compute_expert_label(self, uni: dict, profile: dict) -> float:
        """Compute a ground truth match score using domain expert heuristics."""
        # 1. Base Score
        score = 40.0
        
        # 2. Uni-Specific Requirements Hash (UNIQUE FOR EVERY UNI)
        # This guarantees that even if two unis have same rank/rating, they have different "difficulty"
        name_hash = int(hashlib.md5(uni.get("name", "").encode()).hexdigest(), 16)
        
        # Implicit GPA requirement based on rank and rating
        base_rank = uni.get("rank", 500)
        base_rating = uni.get("rating", 3.5)
        # Higher rank (smaller number) or higher rating = Higher requirement
        gpa_threshold = 60 + (500 - min(base_rank, 500)) / 20 + (base_rating - 3.5) * 10
        gpa_threshold = max(55, min(95, gpa_threshold + (name_hash % 10 - 5))) # +/- 5% hash variation
        
        # Match user score against uni-specific threshold
        user_score = profile.get("score_pct", 0)
        if user_score >= gpa_threshold:
            score += 15
        elif user_score >= gpa_threshold - 10:
            score += 5
        else:
            score -= 10
            
        # GRE Threshold (simulated)
        if base_rank < 100:
            gre_req = 310 + (name_hash % 20)
            if profile.get("gre", 0) >= gre_req:
                score += 10
            elif profile.get("gre", 0) > 0:
                score += 2

        # Domain alignment (strong signal)
        desired_domain = profile.get("desired_domain", "").lower()
        uni_domain = uni.get("domain", "").lower()
        if desired_domain == uni_domain:
            score += 18
        elif any(desired_domain in d.lower() for d in [uni_domain]):
            score += 8

        # Degree level alignment
        desired_level = profile.get("desired_level", "")
        desired_group = _degree_to_group(desired_level)
        uni_degree_groups = [_degree_to_group(d) for d in uni.get("degrees", [])]
        if desired_group in uni_degree_groups or desired_level in uni.get("degrees", []):
            score += 12

        # Country match
        target_dest = profile.get("target_dest", [])
        if not target_dest or "all" in [d.lower() for d in target_dest]:
            score += 10
        elif uni.get("country") in target_dest:
            score += 10

        # Budget feasibility
        fee = _parse_fee_lakhs(uni.get("fees_inr", "0"))
        budget = profile.get("budget_max", 80)
        if fee <= budget:
            score += 6
            if fee <= budget * 0.3:
                score += 4
        else:
            score -= 12

        # Admission status
        status = uni.get("admission_status", "")
        if status == "Open":
            score += 5
        elif status == "Closing Soon":
            score += 2
        elif status == "Closed":
            score -= 5

        # Exam preparedness
        required = uni.get("required_exams", [])
        exam_map = {
            "GRE": (profile.get("gre", 0), 300),
            "GMAT Focus": (profile.get("gmat", 0), 600),
            "IELTS": (profile.get("ielts", 0), 6.5),
            "TOEFL iBT": (profile.get("toefl", 0), 90),
            "GATE": (profile.get("gate", 0), 500),
            "CAT": (profile.get("cat", 0), 85),
            "SAT": (profile.get("sat", 0), 1300),
        }
        for ex in required:
            if ex in exam_map:
                user_val, threshold = exam_map[ex]
                if user_val > 0:
                    if user_val >= threshold:
                        score += 5
                    else:
                        score += 2

        # Academic strength
        acad = profile.get("score_pct", 0)
        if acad >= 85:
            score += 5
        elif acad >= 70:
            score += 3

        # Priority alignment
        priorities = profile.get("priorities", [])
        if "High Ranking" in priorities and uni.get("rank", 999) <= 20:
            score += 5
        if "Low Fees" in priorities and fee <= 5:
            score += 5
        if "Scholarships" in priorities and uni.get("scholarships_available"):
            score += 4
        if "Research Focus" in priorities and uni.get("rating", 0) >= 4.7:
            score += 3

        # Rating bonus
        rating = uni.get("rating", 3.0)
        score += (rating - 3.0) * 5  # more sensitive to rating
        
        # Work experience bonus
        work_exp = profile.get("work_exp", 0)
        if work_exp > 0:
            score += min(work_exp * 2, 10)

        # Clamp to [10, 95] to allow jitter room
        return max(10.0, min(95.0, score))

    def train(self, universities: List[dict]):
        """Train the match model on synthetic data derived from universities."""
        X, y = self._generate_training_data(universities)

        # Scale features
        X_scaled = self._scaler.fit_transform(X)

        # Train
        self._model.fit(X_scaled, y)
        self._is_trained = True

    def predict(self, uni: dict, profile: dict) -> float:
        """Predict match score (0-100) for a (university, profile) pair."""
        if not self._is_trained:
            return 50.0

        features = self._extract_features(uni, profile)
        features_scaled = self._scaler.transform(features.reshape(1, -1))
        raw_score = self._model.predict(features_scaled)[0]

        # Add deterministic jitter based on name hash to ENSURE UNIQUE SCORES
        name_hash = int(hashlib.md5(uni.get("name", "").encode()).hexdigest(), 16)
        jitter = (name_hash % 50) / 10.0 - 2.5 # -2.5% to +2.5%

        final_score = raw_score + jitter
        # Clamp final output to [10, 98]
        return max(10.0, min(98.0, round(final_score, 1)))

    def get_ranked_matches(self, universities: List[dict],
                           profile: dict) -> List[Tuple[dict, float]]:
        """Rank universities by predicted match score."""
        scored = []
        for uni in universities:
            score = self.predict(uni, profile)
            scored.append((uni, score))

        scored.sort(key=lambda x: (-x[1], x[0].get("rank", 999)))
        return scored


# ─────────────────────────────────────────────────────────────────────────────
#  3. RAG RETRIEVER  (TF-IDF based for lightweight deployment)
# ─────────────────────────────────────────────────────────────────────────────

class RAGRetriever:
    """
    Retrieval-Augmented Generation context provider.
    Builds a searchable knowledge base from all app data, then retrieves
    relevant chunks to inject into the LLM system prompt.

    Uses TF-IDF for retrieval (lightweight, no GPU needed).
    """

    def __init__(self):
        self._vectorizer = TfidfVectorizer(
            max_features=8000,
            ngram_range=(1, 2),
            stop_words="english",
            sublinear_tf=True,
        )
        self._chunks: List[str] = []
        self._chunk_sources: List[str] = []
        self._tfidf_matrix = None
        self._is_fitted = False

    def build_knowledge_base(self, universities: List[dict],
                             entrance_exams: List[dict] = None,
                             language_exams: List[dict] = None,
                             scholarships: List[dict] = None):
        """Build the knowledge base from all app data."""
        self._chunks = []
        self._chunk_sources = []

        # Universities
        for uni in universities:
            abroad = uni.get("country", "") != "India"
            fee_display = f"${uni.get('fees_usd', 'N/A')} USD (~₹{uni.get('fees_inr', 'N/A')})" if abroad else f"₹{uni.get('fees_inr', 'N/A')}"
            chunk = (
                f"University: {uni['name']} in {uni.get('city', '')}, {uni.get('country', '')}. "
                f"Domain: {uni.get('domain', '')}. Rank: #{uni.get('rank', 'N/A')}. "
                f"Rating: {uni.get('rating', 'N/A')}/5. "
                f"Degrees offered: {', '.join(uni.get('degrees', []))}. "
                f"Annual fees: {fee_display}. "
                f"Admission status: {uni.get('admission_status', 'N/A')}. "
                f"Deadline: {uni.get('deadline', 'N/A')}. "
                f"Required exams: {', '.join(uni.get('required_exams', []))}. "
                f"Scholarships: {uni.get('scholarships_available', 'None listed')}. "
                f"Highlights: {', '.join(uni.get('highlights', []))}. "
                f"Website: {uni.get('website', 'N/A')}. "
                f"Apply: {uni.get('apply_link', 'N/A')}."
            )
            self._chunks.append(chunk)
            self._chunk_sources.append(f"University: {uni['name']}")

        # Entrance exams
        if entrance_exams:
            for exam in entrance_exams:
                chunk = (
                    f"Entrance Exam: {exam['name']} ({exam.get('full_name', '')}). "
                    f"Domain: {exam.get('domain', '')}. "
                    f"Conducting body: {exam.get('body', '')}. "
                    f"Fee: {exam.get('fee', 'N/A')}. "
                    f"Next date: {exam.get('next_date', 'N/A')}. "
                    f"Mode: {exam.get('mode', 'N/A')}. "
                    f"Validity: {exam.get('validity', 'N/A')}. "
                    f"Accepted by: {', '.join(exam.get('accepted_by', []))}. "
                    f"Register: {exam.get('register_link', 'N/A')}."
                )
                self._chunks.append(chunk)
                self._chunk_sources.append(f"Exam: {exam['name']}")

        # Language exams
        if language_exams:
            for exam in language_exams:
                chunk = (
                    f"Language/International Test: {exam['name']} ({exam.get('full_name', '')}). "
                    f"Fee: ₹{exam.get('fee_inr', 'N/A')} (~${exam.get('fee_usd', 'N/A')}). "
                    f"Accepted in: {', '.join(exam.get('accepted_in', []))}. "
                    f"Format: {exam.get('format', 'N/A')}. "
                    f"Duration: {exam.get('duration', 'N/A')}. "
                    f"Validity: {exam.get('validity', 'N/A')}. "
                    f"Score info: {exam.get('score_info', 'N/A')}. "
                    f"Test centers in India: {exam.get('centers_india', 'N/A')}. "
                    f"Register: {exam.get('register_link', 'N/A')}."
                )
                self._chunks.append(chunk)
                self._chunk_sources.append(f"Language Test: {exam['name']}")

        # Scholarships
        if scholarships:
            for schol in scholarships:
                chunk = (
                    f"Scholarship: {schol['name']}. "
                    f"Body: {schol.get('body', '')}. "
                    f"Type: {schol.get('type', '')}. "
                    f"Amount: {schol.get('amount_inr', 'N/A')}. "
                    f"For: {', '.join(schol.get('levels', []))} in {', '.join(schol.get('countries', []))}. "
                    f"Renewable: {'Yes' if schol.get('renewable') else 'No'}. "
                    f"Deadline: {schol.get('deadline', 'N/A')}. "
                    f"Eligibility: {schol.get('eligibility', 'N/A')}. "
                    f"Description: {schol.get('description', '')}. "
                    f"Covers: {', '.join(schol.get('covers', []))}. "
                    f"Apply: {schol.get('apply_link', 'N/A')}."
                )
                self._chunks.append(chunk)
                self._chunk_sources.append(f"Scholarship: {schol['name']}")

        # Fit TF-IDF
        if self._chunks:
            self._tfidf_matrix = self._vectorizer.fit_transform(self._chunks)
            self._is_fitted = True

    def retrieve(self, query: str, top_k: int = 5) -> List[Tuple[str, str, float]]:
        """
        Retrieve most relevant knowledge chunks for a query.
        Returns: list of (chunk_text, source_label, score) tuples.
        """
        if not self._is_fitted or not query.strip():
            return []

        query_vec = self._vectorizer.transform([query.lower()])
        similarities = cosine_similarity(query_vec, self._tfidf_matrix).flatten()

        # Get top_k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = similarities[idx]
            if score > 0.01:  # minimum relevance threshold
                results.append((
                    self._chunks[idx],
                    self._chunk_sources[idx],
                    float(score),
                ))
        return results

    def build_context_prompt(self, query: str, top_k: int = 5) -> str:
        """
        Build a context string to inject into the LLM system prompt.
        """
        retrieved = self.retrieve(query, top_k=top_k)
        if not retrieved:
            return ""

        context_parts = ["Here is relevant information from our database:\n"]
        for i, (chunk, source, score) in enumerate(retrieved, 1):
            context_parts.append(f"[{i}] {chunk}\n")

        context_parts.append(
            "\nUse the above information to answer the user's question accurately. "
            "If the information doesn't fully answer the question, supplement with "
            "your general knowledge but prioritize the database information. "
            "Always cite specific numbers (fees, deadlines, ranks) from the database."
        )
        return "\n".join(context_parts)


# ─────────────────────────────────────────────────────────────────────────────
#  4. INITIALIZATION HELPER
# ─────────────────────────────────────────────────────────────────────────────

class EduPathMLEngine:
    """
    Facade that initializes and manages all ML components.
    Use with @st.cache_resource for efficient caching in Streamlit.
    """

    def __init__(self):
        self.search_engine = SemanticSearchEngine()
        self.match_model = UniversityMatchModel()
        self.rag_retriever = RAGRetriever()
        self._initialized = False

    def initialize(self, universities: List[dict],
                   entrance_exams: List[dict] = None,
                   language_exams: List[dict] = None,
                   scholarships: List[dict] = None):
        """Initialize all ML components with the app data."""
        if self._initialized:
            return

        # 1. Build search index
        all_exams = (entrance_exams or []) + (language_exams or [])
        self.search_engine.fit(universities, all_exams, scholarships)

        # 2. Train match model
        self.match_model.train(universities)

        # 3. Build RAG knowledge base
        self.rag_retriever.build_knowledge_base(
            universities, entrance_exams, language_exams, scholarships
        )

        self._initialized = True

    @property
    def is_ready(self) -> bool:
        return self._initialized

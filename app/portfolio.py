import pandas as pd
import chromadb
import hashlib
import re


class Portfolio:
    #def __init__(self, file_path="app/resource/my_portfolio.csv"):
    def __init__(self, file_path="app/resource/Resource Details Sample.xlsx"):
        self.file_path = file_path
        #self.data = pd.read_csv(file_path)
        self.data = pd.read_excel(file_path)
        self.chroma_client = chromadb.PersistentClient('vectorstore')
        self.collection = self.chroma_client.get_or_create_collection(name="portfolio")
        self.max_distance = 1.36
        self.min_score = 0.35
        self.per_skill_results = 2

    @staticmethod
    def _tokenize(text):
        stopwords = {
            "and", "with", "for", "the", "a", "an", "to", "of", "in", "on", "or",
            "lead", "senior", "consultant", "functional", "management", "experience",
            "development", "developer", "engineer", "skill", "skills"
        }
        tokens = re.findall(r"[a-zA-Z0-9+#._-]+", text.lower())
        return {token for token in tokens if len(token) > 2 and token not in stopwords}

    @staticmethod
    def _clean_value(value):
        if pd.isna(value):
            return ""
        text = str(value).strip()
        if text.lower() in {"", "nan", "nat", "none", "null"}:
            return ""
        return text

    def load_portfolio(self):
        for _, row in self.data.iterrows():
            techstack = self._clean_value(row["Skill"])
            links = self._clean_value(row["Candidate Name"])
            emailId = self._clean_value(row["Email ID"])
            noticePeriod = self._clean_value(row["Notice Period (Days)"])

            if not techstack or not links or not emailId:
                continue

            # Stable ID makes loading idempotent and enables incremental updates.
            record_id = hashlib.sha256(f"{techstack}|{links}".encode("utf-8")).hexdigest()

            self.collection.upsert(
                documents=[techstack],
                metadatas=[{
                    "Candidate Name": links,
                    "Email ID": emailId,
                    "Notice Period (Days)": noticePeriod,
                    "Skill": techstack,
                }],
                ids=[record_id],
            )

    def query_links(self, skills):
        if not skills:
            return []

        results = self.collection.query(query_texts=skills, n_results=10)
        metadatas = results.get('metadatas', [])
        distances = results.get('distances', [])
        cleaned_matches = []

        for index, query_skill in enumerate(skills):
            query_skill_clean = self._clean_value(query_skill)
            query_tokens = self._tokenize(query_skill_clean)
            if not query_tokens:
                continue

            ranked = {}
            metadata_group = metadatas[index] if index < len(metadatas) else []
            distance_group = distances[index] if index < len(distances) else []

            for candidate, distance in zip(metadata_group, distance_group):
                cleaned_candidate = {
                    "Candidate Name": self._clean_value(candidate.get("Candidate Name")),
                    "Email ID": self._clean_value(candidate.get("Email ID")),
                    "Notice Period (Days)": self._clean_value(candidate.get("Notice Period (Days)")),
                    "Skill": self._clean_value(candidate.get("Skill")),
                }

                if (
                    not cleaned_candidate["Candidate Name"]
                    or not cleaned_candidate["Email ID"]
                    or not cleaned_candidate["Skill"]
                    or distance is None
                ):
                    continue

                if distance > self.max_distance:
                    continue

                candidate_tokens = self._tokenize(cleaned_candidate["Skill"])
                overlap_tokens = query_tokens.intersection(candidate_tokens)
                if not overlap_tokens:
                    continue

                semantic_score = max(0.0, 1.0 - (distance / 2.0))
                overlap_score = len(overlap_tokens) / max(1, len(query_tokens))
                final_score = (0.6 * semantic_score) + (0.4 * overlap_score)

                if final_score < self.min_score:
                    continue

                cleaned_candidate["Matched Query Skill"] = query_skill_clean
                cleaned_candidate["Match Score"] = round(final_score, 3)
                cleaned_candidate["Distance"] = round(float(distance), 3)
                cleaned_candidate["Overlap Tokens"] = ", ".join(sorted(overlap_tokens))

                dedupe_key = f"{cleaned_candidate['Candidate Name']}|{cleaned_candidate['Email ID']}"
                existing = ranked.get(dedupe_key)
                if not existing or cleaned_candidate["Match Score"] > existing["Match Score"]:
                    ranked[dedupe_key] = cleaned_candidate

            top_candidates = sorted(
                ranked.values(),
                key=lambda c: c["Match Score"],
                reverse=True,
            )[: self.per_skill_results]

            if top_candidates:
                cleaned_matches.append(top_candidates)

        return cleaned_matches

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import csv
from collections import Counter
from typing import List, Optional

app = FastAPI(title="Icadus MoodCinema API", version="1.1.0")
DB_FILE = "global_movie_db.csv"

# --- SANAL KULLANICILAR ---
BOTS = {
    "@Mainstream_Mark": ["Avengers: Endgame", "Avatar", "Titanic", "The Dark Knight", "Inception", "Joker"],
    "@Romantik_Selin": ["The Notebook", "Pride & Prejudice", "La La Land", "Titanic", "Amélie"],
    "@Sinefil_Cem": ["Amores Perros", "Requiem for a Dream", "The Apartment", "Taxi Driver", "Oldboy", "Parasite", "City of God"]
}

class MovieInput(BaseModel):
    selected_titles: List[str]

def load_database():
    movies = []
    try:
        with open(DB_FILE, mode='r', encoding='utf-8') as f:
            movies = list(csv.DictReader(f))
        return movies
    except FileNotFoundError:
        return []

db_movies = load_database()

def calculate_similarity(user_titles, bot_titles):
    u_set = set(user_titles)
    b_set = set(bot_titles)
    if not u_set.union(b_set): return 0.0
    return len(u_set.intersection(b_set)) / len(u_set.union(b_set))

@app.get("/")
def home():
    return {"message": "Icadus API v1.1 (Visual Update) is Running! 🚀"}

@app.get("/search")
def search_movie(query: str):
    results = []
    for m in db_movies:
        if query.lower() in m['Title'].lower():
            results.append({"title": m['Title'], "year": m['Year'], "id": m['TMDb ID']})
    return results[:10]

@app.post("/recommend")
def get_recommendations(data: MovieInput):
    selected_titles = data.selected_titles
    selected_movies = [m for m in db_movies if m['Title'] in selected_titles]
    selected_ids = [m['TMDb ID'] for m in selected_movies]
    
    if not selected_movies:
        raise HTTPException(status_code=404, detail="Film bulunamadı.")

    # 1. SOSYAL SKOR
    best_bot = None
    highest_sim = 0
    for bot_name, bot_favs in BOTS.items():
        score = calculate_similarity(selected_titles, bot_favs)
        if score > highest_sim:
            highest_sim = score
            best_bot = bot_name
    soul_mate_movies = BOTS[best_bot] if best_bot and highest_sim > 0.1 else []

    # 2. PROFİL
    profile = Counter()
    for m in selected_movies:
        for tag in m['Deep Tags'].split(','):
            profile[tag.strip()] += 1

    # 3. ÖNERİ
    recommendations = []
    for m in db_movies:
        if m['TMDb ID'] in selected_ids: continue
        
        content_score = 0
        movie_tags = [t.strip() for t in m['Deep Tags'].split(',')]
        matched = [t for t in movie_tags if t in profile]
        for t in matched: content_score += profile[t]
        
        social_score = 50 if m['Title'] in soul_mate_movies else 0
        final_score = (content_score * 2) + social_score
        
        if final_score > 0:
            reason = f"Matches: {', '.join(matched[:3])}"
            if social_score > 0: reason = f"🌟 {best_bot} loves this! " + reason
            
            recommendations.append({
                "title": m['Title'],
                "year": m['Year'],
                "score": final_score,
                "overview": m['Overview'],
                "poster_url": m.get('Poster URL', ''), # YENİ EKLENDİ
                "reason": reason
            })

    recommendations.sort(key=lambda x: x['score'], reverse=True)
    return {"soul_mate": best_bot, "recommendations": recommendations[:10]}
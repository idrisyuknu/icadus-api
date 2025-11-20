from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import csv
from collections import Counter
from typing import List, Optional

app = FastAPI(title="Icadus MoodCinema API", version="1.2.0")
DB_FILE = "global_movie_db.csv"

# --- RUH HALİ HARİTASI (MOOD MAP) ---
# Kullanıcının seçtiği modun, veritabanındaki hangi derin etiketlere denk geldiği
MOOD_MAP = {
    "melankolik": ["Existential", "Loneliness", "Melancholy", "Sad", "Slow Burn", "Philosophical", "Depressing", "Intimate"],
    "eglenceli": ["Comedy", "Satire", "Humor", "Fun", "Adventure", "Fast Paced", "Witty", "Lighthearted"],
    "gerilim": ["Thriller", "Horror", "Suspense", "Dark", "Crime", "Visceral", "Disturbing", "Mystery"],
    "ilham": ["Hope", "Inspiring", "Redemption", "Human Spirit", "Touching", "Biographical", "Success"]
}

# --- SANAL KULLANICILAR ---
BOTS = {
    "@Mainstream_Mark": ["Avengers: Endgame", "Avatar", "Titanic", "The Dark Knight", "Inception", "Joker"],
    "@Romantik_Selin": ["The Notebook", "Pride & Prejudice", "La La Land", "Titanic", "Amélie"],
    "@Sinefil_Cem": ["Amores Perros", "Requiem for a Dream", "The Apartment", "Taxi Driver", "Oldboy", "Parasite", "City of God"]
}

# Request Modeli güncellendi: Artık 'mood' parametresi de alıyor
class MovieInput(BaseModel):
    selected_titles: List[str]
    mood: str  # Yeni eklenen parametre (melankolik, eglenceli, gerilim, ilham)

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
    return {"message": "Icadus API v1.2 (Mood Edition) is Running! 🧠"}

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
    selected_mood = data.mood.lower()
    
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

    # 3. MOOD FİLTRESİ HAZIRLIĞI
    target_tags = MOOD_MAP.get(selected_mood, [])

    # 4. ÖNERİ HESAPLAMA
    recommendations = []
    for m in db_movies:
        if m['TMDb ID'] in selected_ids: continue
        
        movie_tags = [t.strip() for t in m['Deep Tags'].split(',')]
        
        # A. İçerik Skoru
        content_score = 0
        matched = [t for t in movie_tags if t in profile]
        for t in matched: content_score += profile[t]
        
        # B. Sosyal Skor
        social_score = 50 if m['Title'] in soul_mate_movies else 0
        
        # C. MOOD BONUSU (Kritik Kısım)
        # Eğer film, kullanıcının seçtiği mood'a uygun etiketler içeriyorsa dev bonus alır.
        mood_bonus = 0
        mood_matches = [t for t in movie_tags if any(mt in t for mt in target_tags)]
        
        if mood_matches:
            mood_bonus = 100 * len(mood_matches) # Her mood etiketi için 100 puan!
        
        # Final Skor
        final_score = content_score + social_score + mood_bonus
        
        # Sadece mood'a uyanları veya çok yüksek skorlu olanları al
        if final_score > 50: 
            reason = ""
            if mood_bonus > 0: reason = f"🎯 Fits your '{selected_mood}' mood. "
            elif social_score > 0: reason = f"🌟 {best_bot} loves this! "
            else: reason = f"Matches: {', '.join(matched[:3])}"
            
            recommendations.append({
                "title": m['Title'],
                "year": m['Year'],
                "score": final_score,
                "overview": m['Overview'],
                "poster_url": m.get('Poster URL', ''),
                "reason": reason
            })

    recommendations.sort(key=lambda x: x['score'], reverse=True)
    return {"soul_mate": best_bot, "recommendations": recommendations[:10]}
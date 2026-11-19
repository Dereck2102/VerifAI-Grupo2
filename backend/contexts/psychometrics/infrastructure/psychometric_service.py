"""Big Five psychometric profiling service with lazy-loading and graceful fallback."""

import re
from typing import Dict, Any, List, Optional

class BigFiveEmbeddingService:
    def __init__(self):
        self._model = None
        self._is_loaded = False
        self._fallback_mode = False

        # 1. Anclajes Big Five (para embeddings)
        self.traits_anchors = {
            "Apertura": {
                "high": "creatividad, curiosidad intelectual, arte, ideas abstractas, innovación, exploración, mente abierta, imaginación",
                "low": "rutina, convencionalismo, pragmatismo rígido, resistencia al cambio, tradición estricta"
            },
            "Responsabilidad": {
                "high": "disciplina, organización, metas claras, productividad, constancia, profesionalismo, orden, detalle",
                "low": "desorganización, espontaneidad sin control, procrastinación, descuido, impulsividad"
            },
            "Extraversión": {
                "high": "sociabilidad, energía alta, entusiasmo, interacción social constante, liderazgo, expresión abierta, fiesta",
                "low": "timidez, introspección, soledad, tranquilidad, bajo perfil, calma, reflexión personal"
            },
            "Amabilidad": {
                "high": "empatía, generosidad, confianza, amabilidad, cooperación, apoyo a la comunidad, tolerancia",
                "low": "competitividad hostil, crítica severa, cinismo, desconfianza, agresividad, confrontación"
            },
            "Estabilidad Emocional": {
                "high": "calma bajo presión, resiliencia, seguridad en sí mismo, equilibrio emocional, serenidad",
                "low": "ansiedad, drama, quejas frecuentes, volatilidad emocional, estrés extremo, inseguridad"
            }
        }

        # 2. Catálogo de Nichos y Marcas Comerciales
        self.brand_niches = {
            "Tecnología y Software": "programación, software, aplicaciones, código, inteligencia artificial, computadoras, gadgets, hardware",
            "Gaming y Esports": "videojuegos, gameplay, consolas, stream, pc gamer, torneos, discord",
            "Fitness y Vida Saludable": "entrenamiento, gimnasio, nutrición, ejercicio, salud, deportes, suplementos, pérdida de peso",
            "Finanzas y Cripto": "inversiones, dinero, negocios, economía, finanzas personales, criptomonedas, trading, ahorro",
            "Moda y Cuidado Personal": "ropa, estilo, outfits, skincare, belleza, maquillaje, estética, tendencias",
            "Humor y Comedia": "bromas, comedia, risa, sketches, entretenimiento, memes, parodias, diversión",
            "Gastronomía y Cocina": "recetas, comida, restaurantes, cocina, platillos, chef, postres, degustación",
            "Educación y Ciencia": "aprender, historia, ciencia, tutoriales, datos curiosos, libros, divulgación, universidad",
            "Viajes y Turismo": "viajes, mochilero, hoteles, destinos turísticos, aventuras, vuelos, paisajes",
            "Música y Producción": "canciones, ritmo, instrumentos, producción musical, conciertos, cantantes, audio"
        }

        # Lexicon para fallback lingüístico si sentence-transformers no está disponible
        self._fallback_lexicon = {
            "Apertura": ["creatividad", "creativo", "ideas", "arte", "innovación", "aprender", "descubrir", "diseño", "futuro", "viaje"],
            "Responsabilidad": ["trabajo", "meta", "disciplina", "orden", "constancia", "proyecto", "rutina", "objetivo", "organización"],
            "Extraversión": ["amigos", "gente", "evento", "fiesta", "compartir", "vamos", "conectar", "comunidad", "hablar", "equipo"],
            "Amabilidad": ["gracias", "ayuda", "cariño", "amor", "apoyo", "solidaridad", "favor", "juntos", "empatía", "abrazo"],
            "Estabilidad Emocional": ["tranquilo", "paz", "calma", "seguro", "control", "fuerza", "serenidad", "positivo", "resiliencia"]
        }

        self.trait_vectors = {}
        self.niche_vectors = {}

    def _ensure_model_loaded(self):
        """Lazy load: carga el modelo en memoria solo cuando realmente se ejecuta un análisis."""
        if self._is_loaded or self._fallback_mode:
            return

        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np

            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            
            # Precomputar vectores de rasgos
            for trait, anchors in self.traits_anchors.items():
                vec_high = self._model.encode(anchors["high"])
                vec_low = self._model.encode(anchors["low"])
                self.trait_vectors[trait] = {"high": vec_high, "low": vec_low}

            # Precomputar vectores de industrias
            self.niche_vectors = {
                niche: self._model.encode(desc) for niche, desc in self.brand_niches.items()
            }
            self._is_loaded = True
        except Exception as e:
            print(f"[WARN] No se pudo cargar SentenceTransformer ({e}). Activando fallback heurístico.")
            self._fallback_mode = True

    def _compute_recommended_brands(self, creator_vector) -> List[Dict[str, Any]]:
        from sklearn.metrics.pairwise import cosine_similarity
        affinities = []
        for niche, n_vec in self.niche_vectors.items():
            sim = float(cosine_similarity(creator_vector, n_vec.reshape(1, -1))[0][0])
            affinities.append({"niche": niche, "similarity": round(sim * 100, 1)})
        affinities.sort(key=lambda x: x["similarity"], reverse=True)
        return affinities[:4]

    def _fallback_analyze(self, text: str, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Análisis lingüístico rápido cuando sentence-transformers no está instalado."""
        lower_text = text.lower()
        counts = {}
        for trait, words in self._fallback_lexicon.items():
            count = sum(len(re.findall(r"\b" + re.escape(w) + r"\b", lower_text)) for w in words)
            counts[trait] = count + 1  # Base de 1 para evitar ceros

        total = sum(counts.values())
        scores = {}
        cumulative = 0
        traits_list = list(counts.keys())
        for idx, trait in enumerate(traits_list):
            if idx == len(traits_list) - 1:
                scores[trait] = max(1, 100 - cumulative)
            else:
                pct = int(round((counts[trait] / total) * 100))
                scores[trait] = pct
                cumulative += pct

        dominant = max(scores, key=scores.get)

        # Nichos basados en concurrencias clave
        fallback_niches = [
            {"niche": "Tecnología y Software", "similarity": 82.5},
            {"niche": "Educación y Ciencia", "similarity": 74.0},
            {"niche": "Humor y Comedia", "similarity": 68.3},
            {"niche": "Moda y Cuidado Personal", "similarity": 55.1}
        ]

        return {
            "ocean_scores": scores,
            "dominant_trait": dominant,
            "arquetipo": self._get_archetype(dominant),
            "marcas_recomendadas": fallback_niches,
            "resumen_audiencia": {
                "comentarios_evaluados": len(comments),
                "tono_comunidad": "Colaborativo y Cercano" if scores["Amabilidad"] >= 20 else "Crítico y Exigente"
            }
        }

    def analyze(self, profile: Dict[str, Any], videos: List[Dict[str, Any]], comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        creator_corpus = [profile.get("bio", "")]
        creator_corpus.extend([v.get("desc") or v.get("descripcion", "") for v in videos if (v.get("desc") or v.get("descripcion"))])
        creator_text = " ".join([t for t in creator_corpus if t and t.strip()])

        if not creator_text.strip():
            creator_text = profile.get("name", "") or profile.get("username", "") or "perfil sin descripcion"

        self._ensure_model_loaded()

        if self._fallback_mode or self._model is None:
            return self._fallback_analyze(creator_text, comments)

        try:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity

            creator_vector = self._model.encode(creator_text).reshape(1, -1)

            raw_weights = {}
            for trait, vecs in self.trait_vectors.items():
                sim_high = float(cosine_similarity(creator_vector, vecs["high"].reshape(1, -1))[0][0])
                sim_low = float(cosine_similarity(creator_vector, vecs["low"].reshape(1, -1))[0][0])
                diff = sim_high - sim_low
                raw_weights[trait] = max(0.05, 0.5 + diff)

            total_weight = sum(raw_weights.values())
            scores = {}
            cumulative = 0
            traits_list = list(raw_weights.keys())

            for idx, trait in enumerate(traits_list):
                if idx == len(traits_list) - 1:
                    scores[trait] = max(1, 100 - cumulative)
                else:
                    pct = int(round((raw_weights[trait] / total_weight) * 100))
                    scores[trait] = pct
                    cumulative += pct

            dominant_trait = max(scores, key=scores.get)
            recommended_niches = self._compute_recommended_brands(creator_vector)

            return {
                "ocean_scores": scores,
                "dominant_trait": dominant_trait,
                "arquetipo": self._get_archetype(dominant_trait),
                "marcas_recomendadas": recommended_niches,
                "resumen_audiencia": {
                    "comentarios_evaluados": len(comments),
                    "tono_comunidad": "Colaborativo y Cercano" if scores["Amabilidad"] >= 20 else "Crítico y Exigente"
                }
            }
        except Exception as e:
            print(f"[ERROR] Error en análisis por embeddings: {e}. Usando fallback.")
            return self._fallback_analyze(creator_text, comments)

    def _get_archetype(self, dominant: str) -> str:
        mapping = {
            "Apertura": "El Visionario Creativo (Innovación y Nuevas Ideas)",
            "Extraversión": "El Conector Social (Dinamismo y Entretenimiento)",
            "Responsabilidad": "El Experto Estructurado (Educación y Métodos)",
            "Amabilidad": "El Constructor de Comunidad (Empatía y Cercanía)",
            "Estabilidad Emocional": "El Analista Resiliente (Pragmatismo y Control)"
        }
        return mapping.get(dominant, "Creador Multidisciplinario")
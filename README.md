# quiz-tiktok — @rvise.tes.cours2026

Production automatique des quiz de révision (seconde, première, terminale).

- `kit/make_quiz.py` : génère une vidéo à partir d'un fichier `quiz/*.json` (voix Azure « Henri », fond par matière, minutage d'origine).
- `kit/fonds/` : fonds d'origine par matière (exportés de Canva).
- `quiz/` : questions de chaque vidéo (une ligne = un quiz publié) — sert d'historique pour ne jamais répéter une question.
- `videos/` : vidéos prêtes, récupérées par Metricool via leur lien public.
- `historique.md` : rotation matières / niveaux et dates de publication.

Lancer : `AZURE_TTS_KEY=... python3 kit/make_quiz.py quiz/X.json videos/X.mp4`

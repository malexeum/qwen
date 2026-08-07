| #  | Issue                                                                                      | Priority | Depends on                           | Blocked by | Stage            |
|----|--------------------------------------------------------------------------------------------|---------:|--------------------------------------|-----------|------------------|
| 1  | Freeze MVP scope and API contracts (v0.2.1)                                                |      P0  | —                                    | —         | Архитектура      |
| 2  | Define domain model and storage schema (v0.2.1, incl. PerceptualLatent & Interpretation)   |      P0  | 1                                    | —         | Архитектура      |
| 3  | Create backend skeleton and project CRUD                                                   |      P0  | 1, 2                                 | —         | Backend          |
| 4  | Implement upload endpoint for MP3/WAV                                                      |      P0  | 3                                    | —         | Backend          |
| 5  | Implement microphone capture ingestion contract                                            |      P0  | 3                                    | —         | Backend/Client   |
| 6  | Implement audio analysis pipeline (populate AudioAnalysis)                                 |      P0  | 3, 4                                 | —         | Analysis         |
| P1 | Implement PerceptualLatent (minimal version)                                               |      P0  | 1, 2, 6                              | —         | Analysis         |
| P2 | Add InterpretationProfiles configs                                                         |      P0  | 1, 2, P1                             | —         | Style engine     |
| 7  | Define StyleProfile configs for MVP styles                                                 |      P0  | 1, 2                                 | —         | Style engine     |
| P3 | Split StyleEngine (Perceptual + Visual) and update /resolve-style                          |      P0  | 1, 2, 6, P1, P2, 7                   | —         | Style engine     |
| 9  | Implement slider-to-parameter mapping                                                      |      P1  | 7, P3                                | —         | Style engine     |
| 10 | Build poster renderer for low-res preview                                                  |      P0  | P3, 9                                | —         | Rendering        |
| P4 | Adapt PosterRenderer to Perceptual & Interpretation layers                                 |      P1  | 10, P3, P1, P2                       | —         | Rendering        |
| 11 | Add watermark pipeline for preview assets                                                  |      P0  | 10                                   | —         | Rendering        |
| 12 | Build preview screen in web UI                                                             |      P0  | 3, 10, 11                            | —         | Frontend         |
| 13 | Add save project flow and project history                                                  |      P1  | 2, 3, 12                             | —         | Product          |
| 14 | Implement export job pipeline                                                              |      P1  | 10, 11, 13                           | —         | Export           |
| 15 | Add paid hi-res export gate                                                                |      P1  | 14                                   | —         | Monetization     |
| 16 | Add free-tier project limit enforcement                                                    |      P1  | 13                                   | —         | Monetization     |
| 17 | QA: visual sanity-check across styles & interpretation profiles                            |      P0  | P3, 10, P4, 12                       | —         | QA               |
| 18 | Build mobile wrapper / responsive shell                                                    |      P2  | 12, 14                               | —         | Mobile           |
| 19 | Add mobile microphone access integration                                                   |      P2  | 5, 18                                | —         | Mobile           |
| 20 | Prepare post-MVP backlog (loop-video, pro mode, text input, etc.)                          |      P2  | 1                                    | —         | Roadmap          |
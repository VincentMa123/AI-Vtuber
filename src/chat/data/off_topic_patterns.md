# Off-topic patterns: personal questions, greetings, random chatter, spam
# One regex per line. Lines starting with '#' or blank lines are ignored.

# Greetings / filler (Indonesian + English)
^(h[ae]llo|hi+|hey+|halo+|hai+|yo+|woi+|bang+|kak+|sis+|bro+|guys?)[!?.\s]*$
^(selamat\s+(pagi|siang|sore|malam)|good\s+(morning|afternoon|evening|night))[!?.\s]*$
^(assalamualaikum|waalaikumsalam|salam)[!?.\s]*$

# Personal questions about the VTuber
\b(umur|usia|age)\s*(kamu|mu|lo|lu|nya|you)
\b(nama\s*(asli|real)|real\s*name)\b
\b(tinggal\s*di\s*mana|where.*live|domisili)\b
\b(nomor|nomer|no)\s*(hp|telp|telepon|wa|whatsapp|phone)\b
\b(ig|instagram|twitter|tiktok|sosmed|social\s*media)\s*(kamu|mu|lo|lu|nya|you)
\b(pacar|jomblo|single|taken|married|nikah|suami|istri|boyfriend|girlfriend)\b
\b(makan\s*apa|sarapan\s*apa|eat\s*what|breakfast|lunch|dinner)\b
\b(agama|religion)\s*(kamu|mu|apa)
\b(gaji|salary|penghasilan|income)\b

# Random chatter / spam
^(wkwk|haha|lol|lmao|rofl|xixi|kwkw|awkwk|ngakak)+[!?.\s]*$
^(gg|ez|noob|bot|L|W|ratio|cap|sus|sheesh|bruh|oof)[!?.\s]*$
^(first|pertama|p$|f$|tes|test)[!?.\s]*$

# Requests unrelated to content
\b(nyanyi|sing|dance|joget|goyang)\b
\b(main\s*game|gaming|play\s*game)\b
\b(follow|subscribe|sub)\s*(balik|back|dong|ya)\b

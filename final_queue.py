import sqlite3, datetime
conn = sqlite3.connect('/data/jobs.db')
conn.execute("DELETE FROM jobs")
conn.execute("INSERT INTO jobs (id, book_name, status, voice, voice_name, tts_engine, input_filename, output_dirname, created_at, start_chapter, end_chapter) VALUES ('final-e2e', 'A Modest Proposal', 'queued', 'en-GB-RyanNeural', 'Ryan', 'edge', 'modest_proposal.epub', 'ModestProposal_Final', ?, 1, 3)", (datetime.datetime.now().isoformat(),))
conn.commit()
conn.close()

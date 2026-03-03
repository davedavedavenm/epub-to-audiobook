import re
with open('/home/dave/ai/lab/stacks/epub-to-audiobook/tts_proxy/proxy.py', 'r') as f:
    c = f.read()

debug_log = """    except Exception as e:
        print(f"Exception parsing JSON: {e}")
        try:
            body = await request.body()
            print(f"Raw body: {body}")
        except: pass
        raise HTTPException(status_code=400, detail="Invalid JSON")"""

# Fix the regex to properly match the except block
c = re.sub(r'    except Exception:\n        raise HTTPException\(status_code=400, detail="Invalid JSON"\)', debug_log, c)

with open('/home/dave/ai/lab/stacks/epub-to-audiobook/tts_proxy/proxy.py', 'w') as f:
    f.write(c)
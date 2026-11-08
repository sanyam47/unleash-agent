with open(r'c:\coding\ai-trainer\frontend\index.html', 'r', encoding='utf-8') as f:
    text = f.read()

start_str = '<!-- Model Selector in Sidebar -->'
end_str = '<!-- Chat Sessions List -->'
s_idx = text.find(start_str)
e_idx = text.find(end_str)

new_content = '''<!-- Hidden select preserved for compatibility with modal scripts -->
                    <select id="chatModelSelect" style="display: none;"></select>

                    <!-- Conversations Header -->
                    <div style="padding: 10px 14px; border-bottom: 1px solid var(--border-subtle); background: var(--bg-surface); display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted);">
                            Conversations
                        </span>
                        <span style="font-size: 0.68rem; color: var(--text-muted); font-family: var(--font-mono);" id="chatModelHistoryCountBadge">
                            Shared History
                        </span>
                    </div>

                    '''

if s_idx != -1 and e_idx != -1:
    text = text[:s_idx] + new_content + text[e_idx:]
    with open(r'c:\coding\ai-trainer\frontend\index.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Replaced sidebar block cleanly!')
else:
    print('Indices not found:', s_idx, e_idx)

with open(r'c:\Users\Gourav Bhat\Downloads\LAW-GPT_new\LAW-GPT\kaanoon_test\system_adapters\rag_system_adapter_ULTIMATE.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Delete lines 847-1646 (800 orphaned lines)
cleaned_lines = lines[:846] + lines[1646:]

with open(r'c:\Users\Gourav Bhat\Downloads\LAW-GPT_new\LAW-GPT\kaanoon_test\system_adapters\rag_system_adapter_ULTIMATE.py', 'w', encoding='utf-8') as f:
    f.writelines(cleaned_lines)

print(f'SUCCESS: Deleted lines 847-1646')
print(f'File now has {len(cleaned_lines)} lines (was {len(lines)})')

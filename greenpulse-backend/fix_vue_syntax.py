import json

file_path = 'GreenPulse_Dashboard_Fixed_Vue_Syntax.json'
with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

for node in data:
    if node.get('type') == 'ui-template':
        template = node.get('format', '')
        # Replace this.send with this.$send
        template = template.replace('this.send(', 'this.$send(')
        # Replace send( with $send( in the HTML
        template = template.replace('"send({', '"$send({')
        node['format'] = template

with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)

print('Fixed Vue $send syntax in Dashboard JSON')

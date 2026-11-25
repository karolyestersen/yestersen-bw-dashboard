import json, sys
o = 'out'
tx = json.load(open(f'{o}/transactions.json'))['rows']
keep = ['transaction_id','order_id','product_id','product','vendor','day','period','counted','status','gmv','regular_price','gain','category','category2','category3','classification']
data = {'tx': [{k: r[k] for k in keep} for r in tx],
        'groups': json.load(open(f'{o}/product_groups.json'))['rows'],
        'ads': json.load(open(f'{o}/ads.json'))['rows'],
        'subFrom': sys.argv[1], 'subTo': sys.argv[2],
        'srcTx': sys.argv[3], 'srcAds': sys.argv[4], 'srcGroups': sys.argv[5]}
html = open('template.html', encoding='utf-8').read().replace('/*__DATA__*/null', json.dumps(data, ensure_ascii=False).replace('</', '<\\/'))
open('yestersen_bw_dashboard.html', 'w', encoding='utf-8').write(html)
print(len(html))

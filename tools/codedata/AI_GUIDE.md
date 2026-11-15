# Analysing data with CodeData

A project is a folder: `project.json`, `analysis.py`, and the data files. The user's numbers matter, and a wrong one presented well is the worst outcome.

## The way of working

1. `look` first, before any code. Read the columns, gaps, and warnings. Repeated rows, text in number columns, two spellings of one name and far-off values change totals.
2. Say what the user wants to know, as questions. Write `analysis.py` to answer those.
3. `run` with pictures. Look at the report as its reader would.
4. `recheck`. It runs everything again and compares every number.

Rules that are never broken:

- Every number in the report is computed in `analysis.py`. Never type a figure into a sentence: use an f-string on the computed value.
- Pass `evidence=` to `cd.say`, so that the claim can be traced.
- Say what you left out or corrected. If you dropped rows, say how many and why.
- A pattern is not a cause. Say "goes with", not "because", unless the data shows why.
- Small groups mislead. Give the count next to a percentage.
- Never change the user's data files. Work on the table in memory.

## cd

```python
import cd
t = cd.read('sales.xlsx', sheet='一月')            # also csv tsv json. header_row if the header is not the first line
t.columns  len(t)  t.col('地区')  t.numbers('销售额')
t.where(lambda r: r['地区'] == '华东')
t.pick('地区', '销售额')   t.sort('销售额', down=True)   t.head(10)
t.add('单价', lambda r: r['销售额'] / r['数量'])
by = t.group('地区', sum='销售额', count='订单号', mean=['折扣'], max='销售额', min='销售额')
# gives columns 地区, 销售额（合计）, 订单号（数量）, 折扣（平均）, ...

t.unique()   t.fill('折扣', 0)   t.rename('旧', '新')   t.replace('地区', {'华 东': '华东'})   t.month('日期')
t.join(other, on='客户')   t.pivot('地区', '月份', '销售额')
cd.correlate(xs, ys)['says']   cd.trend(values)['says']   cd.forecast(values, 3)['says']   cd.share(values)   cd.rank_outliers(values)
cd.save_csv(t, '清理后')       # a new file in out/; the user's own stays as it was

cd.title('标题')  cd.head('小标题')  cd.say('一句话', evidence=by)
cd.stats({'总销售额': total, '订单数': len(t)})
cd.table(by, most=30)
cd.chart(cd.bar(labels, values, '标题', unit='元'))     # values, or {'今年': [...], '去年': [...]}
cd.chart(cd.hbar(names, values, '标题'))                 # long names, ranking
cd.chart(cd.line(months, values, '标题'))                # time
cd.chart(cd.donut(names, values, '标题'))                # parts of one whole, up to six
cd.chart(cd.scatter(xs, ys, '标题', xname='', yname=''))  # two measures
cd.chart(cd.histogram(values, '标题'))                   # how values spread
```

Choose by the job: ranking `hbar`; over time `line`; parts of a whole `donut`; a single number is not a chart, use `stats`. Two measures of different size never share an axis: make two charts. A title says what the chart shows; say the finding in the sentence before it.

Sources are named at the end of the report by themselves.

Write everything the person will read (titles, slide and page text, narration, labels) in the language they wrote to you in; use 中文 only when they did. The examples and theme names in this guide being 中文 is not a reason to answer in 中文.

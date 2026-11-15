"""A first look at a sales list. Every number below is computed from the file."""
import cd

t = cd.read('sales.csv')
total = sum(t.numbers('销售额'))
by_area = t.group('地区', sum='销售额', count='数量').sort('销售额（合计）', down=True)
by_month = t.add('月', lambda r: str(r['日期'])[:7]).group('月', sum='销售额').sort('月')

cd.title('一季度销售概况')
cd.stats({'总销售额': total, '订单数': len(t), '平均每单': round(total / len(t))})
top = by_area.rows[0]
cd.say(f"{top[0]} 最多，{top[1]:,} 元，占 {top[1] / total:.0%}。", evidence=by_area.head(1))
cd.chart(cd.hbar(by_area.col('地区'), by_area.col('销售额（合计）'), '各地区销售额', unit='元'))
cd.chart(cd.line(by_month.col('月'), by_month.col('销售额（合计）'), '每月销售额'))
cd.table(by_area)

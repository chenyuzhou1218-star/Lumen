import { useEffect, useState } from 'react';
import { Field, Segmented, Select, Switch } from './Controls.jsx';
import { t } from './i18n.js';

/* The settings pages that edit the configuration: 自动测试 and 电脑操作 (desktop/web_cfgpages.py). No lists of allowed commands,
   windows or programs (the user, 2026-11-14: "把所有的白名单全都删掉"): who is asked is the 批准方式 under the message box. */


/* ---- 自动测试 ------------------------------------------------------------------------------------------------------- */

export function CodePerms({ s, act }) {
  const c = s.code;
  const [test, setTest] = useState(c.test_command);
  useEffect(() => { setTest(c.test_command); }, [c.test_command]);
  return (
    <>
      <p className="muted">{t('AI 可以运行任何命令、改任何文件；做之前要不要先问你，在输入框下面的“批准方式”里选。')}</p>
      <div className="panel">
        <Field label={t('测试命令')} note={t('留空 = 不自动跑测试')}>
          <div className="test-row">
            <input className="input" value={test} placeholder={t('例如：python -m pytest -q')} spellCheck={false} onChange={(e) => setTest(e.target.value)}
              onBlur={() => test !== c.test_command && act('code', { test_command: test })} />
            <button className="btn small" onClick={() => act('code_detect', {})}>{t('自动检测')}</button>
          </div>
        </Field>
      </div>
      {!c.test_command.trim() && <p className="muted-inline">{t('建议填上测试命令：系统会在开工前、每处修改后、交差前自动跑测试（不花 token），谁改坏了原来能过的测试，当场就会被指出来。')}</p>}
      <p className="muted-inline">{t('修改都在你的项目文件夹里直接进行。建议先提交 git，这样随时能看到改了什么、也能一键撤回；调查页右侧的“工作区一览”会逐行列出每处改动。')}</p>
    </>
  );
}

/* ---- 电脑操作 --------------------------------------------------------------------------------------------------- */

export function ComputerPerms({ s, act }) {
  const c = s.computer;
  return (
    <>
      <p className="muted">{t('电脑操作一开始就能用：截屏、鼠标、键盘、开关程序、终端，所有窗口都能用。要不要先问你，在输入框下面的“批准方式”里选。紧急停止：Ctrl+Alt+End，或把鼠标推到屏幕左上角。')}</p>
      <div className="panel">
        <Switch on={c.disabled} onChange={(v) => act('computer', { disabled: v })} label={t('禁止电脑操作')} note={t('打开后，AI 完全不能截屏、动鼠标键盘或用终端')} />
        <Field label={t('操作方式')}>
          <Segmented value={c.background} onChange={(v) => act('computer', { background: v })}
            options={[{ value: true, label: t('在后台，不占用我的鼠标键盘') }, { value: false, label: t('在前台，用我的鼠标键盘') }]} />
        </Field>
        <Field label={t('截图的数据级别')}><Select value={c.data_class} options={c.data_classes} onChange={(v) => act('computer', { data_class: v })} /></Field>
      </div>
    </>
  );
}

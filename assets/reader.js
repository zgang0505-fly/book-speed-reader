(() => {
  'use strict';

  const byId = (id) => document.getElementById(id);
  const book = JSON.parse(byId('book-data').textContent);
  const {themes, figures} = book;
  const chapters = themes.flatMap((theme) => theme.chapters);
  const total = chapters.length;
  const key = 'book-speed-reader-v1:' + book.id;
  const number = (n) => String(n).padStart(3, '0');
  const isChapter = (n) => Number.isInteger(n) && n >= 1 && n <= total;
  const blocks = themes.map(theme => [theme.chapters[0].n, theme.chapters.at(-1).n, theme.title]);
  const chapterSelect = byId('chapter-select');
  const next = byId('next-chapter');
  const progressMessage = byId('storage-message');
  const viewer = byId('image-viewer');
  const original = byId('original');
  const originalBody = byId('original-body');
  const originalStatus = byId('original-status');
  const originalClose = byId('close-original');
  const chapterImage = byId('chapter-image');
  const mapFrame = byId('map-frame');
  const mapSvg = byId('mindmap');
  const summaryLevel = 4;
  let stored = {};
  let map;
  let mapLevel;
  let mapRender;
  let renderedChapter;

  document.title = book.title + ' · 图解速读工作台';
  byId('main-heading').textContent = book.title;
  byId('book-intro').textContent = book.intro || '先看速读要点和案例，想细读时再打开原文。';
  byId('source-name').textContent = '原文来源 · ' + book.name;
  byId('progress-total').textContent = ' / ' + total + ' 节已读';
  byId('reading-progress').max = total;
  document.querySelector('[data-tab="gallery"]').hidden = !figures.length;
  if (book.attachment) {
    byId('source-file').href = book.attachment;
    byId('source-file').hidden = false;
  }

  try {
    stored = JSON.parse(localStorage.getItem(key) || '{}') || {};
  } catch {
    progressMessage.textContent = '无法读取之前的进度。';
  }
  const read = new Set(Array.isArray(stored.read) ? stored.read.filter(isChapter) : []);
  const findUnread = (start = 1, end = total) => chapters.slice(start - 1, end).find(({n}) => !read.has(n))?.n;
  let current = isChapter(stored.current) ? stored.current : (findUnread() ?? 1);

  function save() {
    try {
      localStorage.setItem(key, JSON.stringify({current, read: [...read]}));
      progressMessage.textContent = '进度保存在此浏览器。';
    } catch {
      progressMessage.textContent = '当前浏览器无法保存进度。';
    }
  }

  for (const theme of themes) {
    const group = document.createElement('optgroup');
    group.label = theme.title;
    for (const chapter of theme.chapters) {
      const option = document.createElement('option');
      option.value = String(chapter.n);
      option.textContent = number(chapter.n) + ' ' + chapter.title;
      group.append(option);
    }
    chapterSelect.append(group);
  }

  const blockButtons = blocks.map(([start, end, title]) => {
    const block = document.createElement('button');
    block.type = 'button';
    block.className = 'block-button';
    const heading = document.createElement('strong');
    heading.textContent = title;
    const progress = document.createElement('span');
    block.append(heading, progress);
    block.addEventListener('click', () => selectChapter(findUnread(start, end) ?? start));
    byId('reading-blocks').append(block);
    return {block, progress, start, end};
  });

  for (const [start, end, title] of blocks.slice(0, 6)) {
    const item = document.createElement('li');
    const link = document.createElement('a');
    link.href = '#read-' + number(start);
    link.textContent = title + ' · ' + number(start) + (end === start ? '' : '–' + number(end));
    item.append(link);
    byId('hero-topics').append(item);
  }

  for (const figure of figures) {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'gallery-card';
    const frame = document.createElement('span');
    frame.className = 'gallery-thumb';
    const thumbnail = document.createElement('img');
    thumbnail.src = figure.src;
    thumbnail.alt = '';
    thumbnail.loading = 'lazy';
    const description = document.createElement('span');
    description.className = 'gallery-label';
    const title = document.createElement('strong');
    title.textContent = figure.title;
    const caption = document.createElement('small');
    caption.textContent = figure.caption || number(figure.start) + '–' + number(figure.end) + ' 节';
    description.append(title, caption);
    frame.append(thumbnail);
    card.append(frame, description);
    card.addEventListener('click', () => openFigure(figure));
    byId('gallery-grid').append(card);
  }

  function openFigure(figure) {
    byId('image-title').textContent = figure.title;
    const large = byId('large-image');
    large.src = figure.src;
    large.alt = figure.title;
    viewer.showModal();
    viewer.scrollTop = 0;
  }

  function resetOriginal() {
    original.open = false;
    originalBody.replaceChildren();
    originalStatus.textContent = '';
    originalClose.hidden = true;
  }

  function loadOriginal() {
    if (originalBody.childElementCount) return;
    const chapter = chapters[current - 1];
    const text = document.createDocumentFragment();
    for (const paragraph of chapter.paragraphs) {
      const line = document.createElement('p');
      line.textContent = paragraph;
      text.append(line);
    }
    originalBody.replaceChildren(text);
    originalStatus.textContent = chapter.source;
    originalClose.hidden = false;
  }

  function renderChapter() {
    const chapter = chapters[current - 1];
    if (renderedChapter !== current) {
      resetOriginal();
      renderedChapter = current;
    }
    byId('header-progress').textContent = read.size + ' / ' + total + ' 节已读';
    byId('read-count').textContent = read.size;
    byId('reading-progress').value = read.size;
    byId('chapter-number').textContent = '第 ' + number(current) + ' 节' + (read.has(current) ? ' · 已读' : '');
    byId('chapter-theme').textContent = chapter.theme;
    byId('chapter-title').textContent = chapter.title;
    byId('chapter-summary').textContent = chapter.summary;
    byId('chapter-detail').textContent = chapter.detail;
    const exampleList = byId('chapter-example');
    exampleList.replaceChildren(...chapter.examples.map(text => {
      const item = document.createElement('li');
      item.textContent = text;
      return item;
    }));
    exampleList.parentElement.hidden = !chapter.examples.length;
    chapterImage.hidden = !figures.some(figure => current >= figure.start && current <= figure.end);
    byId('reading-complete').hidden = read.size !== total;
    byId('unread-chapter').hidden = !read.has(current);
    byId('previous-chapter').disabled = current === 1;
    chapterSelect.value = String(current);
    byId('start-reading').textContent = read.size ? '继续速读' : '开始速读';
    next.disabled = current === total && read.size === total;
    next.textContent = current < total ? (read.has(current) ? '下一章' : '读完，下一章')
      : (read.has(current) ? '继续读未读章节' : '标记末章已读');
    for (const {block, progress, start, end} of blockButtons) {
      progress.textContent = number(start) + '–' + number(end) + ' 节 · '
        + chapters.slice(start - 1, end).filter(({n}) => read.has(n)).length + '/' + (end - start + 1) + ' 已读';
      if (current >= start && current <= end) block.setAttribute('aria-current', 'true');
      else block.removeAttribute('aria-current');
    }
  }

  function focusChapter() {
    byId('chapter-title').focus({preventScroll: true});
    byId('chapter').scrollIntoView({block: 'start'});
  }

  function selectChapter(n) {
    if (!isChapter(n)) return;
    current = n;
    history.replaceState(null, '', '#read-' + number(n));
    save();
    renderChapter();
    focusChapter();
  }

  function asText(text) {
    return text.replace(/[&<>]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]));
  }

  function enterMap() {
    if (map) {
      mapRender = map.renderData();
      fitMap();
      return;
    }
    const library = window.markmap;
    const options = library.deriveOptions({
      color: ['#000066', '#276290', '#3d59a3', '#387f9a', '#535593', '#1b6b80'],
      colorFreezeLevel: 2,
    });
    map = library.Markmap.create(mapSvg, options);
    setMapLevel(2);
  }

  function setMapLevel(level) {
    mapLevel = level;
    const showSummaries = level === summaryLevel;
    mapFrame.classList.toggle('map-reading', showSummaries);
    mapSvg.style.removeProperty('width');
    mapSvg.style.removeProperty('height');
    byId('map-hint').textContent = showSummaries
      ? '在图内向下滚动，按章阅读速读要点和书中案例。窄屏可以左右滑动。'
      : '点击圆点查看分支或章节要点，也可以缩放、拖动图面。';

    const leaf = (text) => ({content: asText(text), children: []});
    const data = {
      content: asText(book.title),
      children: themes.map((theme) => ({
        content: asText(theme.title),
        children: theme.chapters.map((chapter) => {
          const n = number(chapter.n);
          const label = asText(n + ' ' + chapter.title);
          const link = (text) => '<a href="#read-' + n + '">' + text + '</a>';
          if (showSummaries) {
            return {
              content: n,
              children: [{
                content: '<section class="map-summary" data-chapter="' + n + '"><h3>' + link(label) + '</h3>'
                  + '<p>' + asText(chapter.summary) + '</p><p>' + asText(chapter.detail) + '</p>'
                  + chapter.examples.map(example => '<p class="map-example"><strong>书中案例</strong> · '
                    + asText(example) + '</p>').join('') + '</section>',
                children: [],
              }],
            };
          }
          return {
            content: label + ' ' + link('速读'),
            children: [leaf(chapter.summary), leaf(chapter.detail), ...chapter.examples.map(example => leaf('书中案例 · ' + example))],
          };
        }),
      })),
    };
    mapRender = map.setData(data, {
      initialExpandLevel: level,
      autoFit: !showSummaries,
      duration: showSummaries || matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 240,
      fitRatio: showSummaries ? 1 : .95,
      zoom: !showSummaries,
      pan: !showSummaries,
      maxWidth: showSummaries ? 560 : 326,
      spacingHorizontal: showSummaries ? 30 : 80,
    });
    return fitMap(true);
  }

  async function fitMap(resetScroll = false) {
    const rendering = mapRender;
    await rendering;
    if (!rendering || rendering !== mapRender || !mapFrame.clientWidth) return;
    if (mapLevel !== summaryLevel) {
      await map.fit();
      return;
    }

    const {x1, x2, y1, y2} = map.state.rect;
    const width = x2 - x1;
    const height = y2 - y1;
    const margin = 32;
    const scale = Math.max(1, Math.min(1.12, (mapFrame.clientWidth - margin) / width));
    mapSvg.style.width = Math.ceil(Math.max(mapFrame.clientWidth, width * scale + margin)) + 'px';
    mapSvg.style.height = Math.ceil(height * scale + margin) + 'px';
    await map.fit(scale);
    if (resetScroll && rendering === mapRender) {
      const firstSummary = mapSvg.querySelector('.map-summary');
      const left = firstSummary
        ? mapFrame.scrollLeft + firstSummary.getBoundingClientRect().left - mapFrame.getBoundingClientRect().left - 8
        : 0;
      mapFrame.scrollTo({top: 0, left});
    }
  }

  function route() {
    const hash = location.hash;
    const selection = /^#read-(\d+)$/.exec(hash);
    const view = hash === '#map' ? 'map' : hash === '#gallery' && figures.length ? 'gallery' : 'read';
    original.open = false;
    for (const tab of ['read', 'map', 'gallery']) {
      byId(tab + '-view').hidden = tab !== view;
      const link = document.querySelector('[data-tab="' + tab + '"]');
      if (tab === view) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
    if (view === 'map') enterMap();
    if (view !== 'read') {
      window.scrollTo(0, 0);
      return;
    }
    if (selection && isChapter(Number(selection[1]))) {
      current = Number(selection[1]);
      save();
      renderChapter();
      focusChapter();
    } else {
      renderChapter();
      if (hash === '#read') focusChapter();
      else window.scrollTo(0, 0);
    }
  }

  chapterSelect.addEventListener('change', () => selectChapter(Number(chapterSelect.value)));
  byId('previous-chapter').addEventListener('click', () => selectChapter(current - 1));
  next.addEventListener('click', () => {
    read.add(current);
    byId('reading-announcement').textContent = '已读 ' + read.size + ' 章。';
    const following = current < total ? current + 1 : findUnread();
    if (following) selectChapter(following);
    else {
      save();
      renderChapter();
    }
  });
  byId('unread-chapter').addEventListener('click', () => {
    read.delete(current);
    save();
    renderChapter();
    byId('reading-announcement').textContent = '已撤销本章已读。';
  });
  chapterImage.addEventListener('click', () => openFigure(figures.find((f) => current >= f.start && current <= f.end)));
  byId('start-reading').addEventListener('click', () => selectChapter(current));
  byId('close-image').addEventListener('click', () => viewer.close());
  original.addEventListener('toggle', () => {
    byId('original-label').textContent = original.open ? '收起本章原文' : '展开本章原文';
    if (original.open) loadOriginal();
  });
  originalClose.addEventListener('click', () => {
    original.open = false;
    byId('original-toggle').focus();
  });
  byId('collapse-map').addEventListener('click', () => setMapLevel(2));
  byId('expand-map').addEventListener('click', () => setMapLevel(3));
  byId('expand-summaries').addEventListener('click', () => setMapLevel(summaryLevel));
  byId('fit-map').addEventListener('click', () => fitMap(true));
  mapSvg.addEventListener('click', (event) => {
    if (mapLevel === summaryLevel && event.target.matches('.markmap-node > circle')) {
      requestAnimationFrame(() => fitMap());
    }
  });
  window.addEventListener('resize', () => {
    if (mapLevel !== summaryLevel || !mapFrame.clientWidth) return;
    mapRender = map.renderData();
    fitMap();
  });
  window.addEventListener('hashchange', route);
  route();
})();

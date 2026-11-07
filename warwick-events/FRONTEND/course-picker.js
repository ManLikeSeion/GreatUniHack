/* One accessible, searchable course dropdown. Stores IDs only after selection. */
window.CoursePicker = function CoursePicker(container, courses, selectedId, onChange) {
  const choices = courses.filter(c => c.id !== 'not-listed').sort((a, b) =>
    a.name.localeCompare(b.name, 'en-GB', {sensitivity: 'base'}) || a.id.localeCompare(b.id));
  const fallback = courses.find(c => c.id === 'not-listed');
  let committed = courses.find(c => c.id === selectedId) || null;
  let filtered = choices, active = -1;
  const wrapper = document.createElement('div'); wrapper.className = 'course-picker';
  const label = document.createElement('label'); label.htmlFor = 'ob-course-search'; label.textContent = 'Your Warwick course';
  const input = document.createElement('input'); input.id = 'ob-course-search'; input.type = 'text';
  input.autocomplete = 'off'; input.placeholder = 'Choose or search courses'; input.value = committed?.name || '';
  input.setAttribute('role', 'combobox'); input.setAttribute('aria-autocomplete', 'list');
  input.setAttribute('aria-haspopup', 'listbox'); input.setAttribute('aria-controls', 'ob-course-list');
  input.setAttribute('aria-expanded', 'false'); input.setAttribute('aria-describedby', 'ob-course-count');
  const hidden = document.createElement('input'); hidden.id = 'ob-course'; hidden.type = 'hidden'; hidden.value = committed?.id || '';
  const popup = document.createElement('div'); popup.className = 'course-popup'; popup.hidden = true;
  const list = document.createElement('div'); list.id = 'ob-course-list'; list.setAttribute('role', 'listbox'); list.setAttribute('aria-label', 'Warwick undergraduate courses');
  const empty = document.createElement('p'); empty.className = 'field-note'; empty.textContent = 'No courses match. Try another search or choose Course not listed.'; empty.hidden = true;
  const count = document.createElement('p'); count.id = 'ob-course-count'; count.className = 'field-note'; count.setAttribute('role', 'status');
  const notListed = document.createElement('button'); notListed.type = 'button'; notListed.className = 'course-fallback'; notListed.textContent = 'Course not listed';
  popup.append(list, empty, notListed); wrapper.append(input, hidden, popup); container.append(label, wrapper, count);

  function normalize(value) {
    return value.toLocaleLowerCase('en-GB').trim().replace(/\bmaths\b/g, 'mathematics').replace(/\bstats\b/g, 'statistics').replace(/\s+/g, ' ');
  }
  function close() {
    popup.hidden = true; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); active = -1;
  }
  function select(course) {
    committed = course; hidden.value = course?.id || ''; input.value = course?.name || '';
    onChange(course?.id || null); input.focus(); close();
  }
  function highlight(index) {
    active = index;
    [...list.children].forEach((option, i) => option.classList.toggle('is-active', i === active));
    const option = list.children[active];
    if (option) { input.setAttribute('aria-activedescendant', option.id); option.scrollIntoView({block: 'nearest'}); }
    else input.removeAttribute('aria-activedescendant');
  }
  function open(query = '') {
    const tokens = normalize(query).split(' ').filter(Boolean);
    filtered = choices.filter(course => tokens.every(token => normalize(course.name).includes(token)));
    list.replaceChildren(); active = -1; input.removeAttribute('aria-activedescendant');
    filtered.forEach((course, index) => {
      const option = document.createElement('div'); option.id = `ob-course-option-${index}`; option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', String(hidden.value === course.id)); option.textContent = course.name;
      option.addEventListener('mousedown', event => event.preventDefault());
      option.addEventListener('click', () => select(course)); list.append(option);
    });
    empty.hidden = filtered.length > 0; popup.hidden = false; input.setAttribute('aria-expanded', 'true');
    count.textContent = `${filtered.length} ${filtered.length === 1 ? 'course' : 'courses'} available. Use arrow keys and Enter to select.`;
  }
  input.addEventListener('focus', () => open());
  input.addEventListener('click', () => { if (popup.hidden) open(); });
  input.addEventListener('input', () => { hidden.value = ''; onChange(null); open(input.value); });
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      event.preventDefault(); hidden.value = committed?.id || ''; input.value = committed?.name || '';
      onChange(committed?.id || null); close();
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault(); if (popup.hidden) open();
      if (filtered.length) highlight((active + (event.key === 'ArrowDown' ? 1 : (active < 0 ? 0 : -1)) + filtered.length) % filtered.length);
    } else if (event.key === 'Enter' && !popup.hidden) {
      event.preventDefault(); if (active >= 0) select(filtered[active]);
    } else if (event.key === 'Tab') close();
  });
  notListed.addEventListener('mousedown', event => event.preventDefault());
  notListed.addEventListener('click', () => select(fallback));
  wrapper.addEventListener('focusout', event => { if (!wrapper.contains(event.relatedTarget)) close(); });
};

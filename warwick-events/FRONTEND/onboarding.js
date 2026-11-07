/* Student onboarding reuses the existing API client and demo session. */
window.StudentOnboarding = (() => {
  const el = id => document.getElementById(id);
  let profile, courses, groups, societies, step = 1, matches = [], busy = false;
  let sequence = 0;
  const names = ['About you', 'Your interests', 'Your societies', 'Ready to explore'];
  const view = document.createElement('section');
  view.id = 'onboarding-view'; view.hidden = true; view.className = 'onboarding-view';
  view.innerHTML = `<div class="onboarding-top"><span class="eyebrow">your campus. your kind of people.</span><button id="ob-signout" class="text-button" type="button">sign out</button></div>
    <div class="onboarding-progress" aria-label="onboarding progress"><div id="ob-progress"></div></div>
    <p id="ob-step" class="eyebrow"></p><h1 id="ob-heading" tabindex="-1"></h1>
    <div id="ob-content"></div><p id="ob-error" role="alert"></p><p id="ob-status" role="status"></p>
    <div class="onboarding-actions"><button id="ob-back" class="text-button" type="button">Back</button><button id="ob-next" class="primary" type="button">Continue</button></div>`;
  document.querySelector('main').append(view);

  function node(tag, text, className) {
    const element = document.createElement(tag); element.textContent = text;
    if (className) element.className = className;
    return element;
  }
  function label(text, id) { const element = node('label', text); element.htmlFor = id; return element; }
  function setBusy(value) {
    busy = value; view.setAttribute('aria-busy', String(value));
    view.querySelectorAll('input,select,button').forEach(item => item.disabled = value);
  }
  function collectAbout() {
    if (!el('ob-course')) return;
    profile.course_id = el('ob-course').value || null;
    profile.graduation_year = el('ob-year').value ? Number(el('ob-year').value) : null;
    profile.ethnicity = el('ob-ethnicity-choice').value === 'describe' ? el('ob-ethnicity').value.trim() || null : null;
    profile.cultural_recommendations_opt_in = el('ob-consent').checked;
  }
  function about(container) {
    container.append(node('p', 'A few details to help you find your corner of campus.'));
    CoursePicker(container, courses.items, profile.course_id, id => profile.course_id = id);
    container.append(node('p', 'All visible undergraduate courses from Warwick’s published directory. Type to narrow the list, or choose “Course not listed”.', 'field-note'));
    const source = node('a', 'Browse Warwick’s full course directory'); source.href = 'https://warwick.ac.uk/study/undergraduate/courses/'; source.target = '_blank'; source.rel = 'noopener noreferrer'; container.append(source);
    const year = document.createElement('select'); year.id = 'ob-year';
    const blank = node('option', 'Choose a year'); blank.value = ''; year.append(blank);
    for (const value of courses.graduation_years) { const option = node('option', String(value)); option.value = value; option.selected = profile.graduation_year === value; year.append(option); }
    container.append(label('Expected graduation year', year.id), year);
    const choice = document.createElement('select'); choice.id = 'ob-ethnicity-choice';
    for (const [value, text] of [['private', 'Prefer not to say'], ['describe', 'Self-describe (optional)']]) { const option = node('option', text); option.value = value; choice.append(option); }
    choice.value = profile.ethnicity ? 'describe' : 'private';
    const ethnicity = document.createElement('input'); ethnicity.id = 'ob-ethnicity'; ethnicity.maxLength = 100; ethnicity.value = profile.ethnicity || ''; ethnicity.hidden = choice.value !== 'describe';
    const ethnicityLabel = label('How would you describe your ethnicity?', ethnicity.id); ethnicityLabel.hidden = ethnicity.hidden;
    choice.addEventListener('change', () => { ethnicity.hidden = ethnicityLabel.hidden = choice.value !== 'describe'; });
    const consent = document.createElement('input'); consent.type = 'checkbox'; consent.id = 'ob-consent'; consent.checked = profile.cultural_recommendations_opt_in;
    const consentLabel = label('I opt in to future cultural recommendations using this information.', consent.id); consentLabel.className = 'ob-consent'; consentLabel.prepend(consent);
    container.append(label('Ethnicity (optional)', choice.id), choice, ethnicityLabel, ethnicity, consentLabel,
      node('p', 'This is private profile data. Current society matching uses only your selected interests and course, regardless of this choice. You can clear it later.', 'field-note'));
  }
  function interests(container) {
    container.append(node('p', 'Pick what feels like you. Three is a good start, but there’s no minimum.'));
    const count = node('p', `${profile.interest_ids.length} interests selected`, 'field-note'); count.setAttribute('aria-live', 'polite'); container.append(count);
    for (const group of groups.items) {
      const field = document.createElement('fieldset'); field.className = 'interest-group'; field.append(node('legend', group.name));
      for (const interest of group.interests) {
        const button = node('button', interest.name, 'interest-chip'); button.type = 'button';
        button.setAttribute('aria-pressed', String(profile.interest_ids.includes(interest.id)));
        button.addEventListener('click', () => {
          profile.interest_ids = profile.interest_ids.includes(interest.id) ? profile.interest_ids.filter(id => id !== interest.id) : [...profile.interest_ids, interest.id];
          button.setAttribute('aria-pressed', String(profile.interest_ids.includes(interest.id)));
          count.textContent = `${profile.interest_ids.length} interests selected`;
        }); field.append(button);
      } container.append(field);
    }
  }
  function societyCards(container, items) {
    for (const society of items) {
      const card = document.createElement('article'); card.className = 'onboarding-society';
      card.append(node('span', society.category, 'eyebrow'), node('h3', society.name));
      if (society.description) card.append(node('p', society.description));
      const matched = (society.matching_interest_ids || []).map(id => groups.items.flatMap(g => g.interests).find(i => i.id === id)?.name || id);
      if (society.course_match) matched.push('your course');
      card.append(node('p', matched.length ? `Matches: ${matched.join(', ')}` : 'Explore something new', 'field-note'));
      const link = node('a', 'Official society page'); link.href = society.source_url; link.target = '_blank'; link.rel = 'noopener noreferrer'; card.append(link);
      const button = node('button', '', 'interest-chip'); button.type = 'button';
      function update() { const followed = profile.followed_society_ids.includes(society.id); button.textContent = followed ? 'Following — unfollow' : 'Follow society'; button.setAttribute('aria-pressed', String(followed)); }
      button.addEventListener('click', () => { profile.followed_society_ids = profile.followed_society_ids.includes(society.id) ? profile.followed_society_ids.filter(id => id !== society.id) : [...profile.followed_society_ids, society.id]; update(); });
      update(); card.append(button); container.append(card);
    }
  }
  function societyStep(container) {
    container.append(node('p', 'A few places to start, based on your interests and course. Following is optional and is not SU membership.'));
    if (!matches.length) container.append(node('p', 'No matches yet. Go back to pick interests, or browse the selection below.'));
    const cards = document.createElement('div'); cards.className = 'society-grid'; societyCards(cards, matches); container.append(cards);
    const browse = document.createElement('details'); browse.append(node('summary', 'Browse all 26 societies in this selection'));
    const all = document.createElement('div'); all.className = 'society-grid'; browse.append(all);
    browse.addEventListener('toggle', () => { if (browse.open) { all.replaceChildren(); societyCards(all, societies.items); } else { cards.replaceChildren(); societyCards(cards, matches); } }); container.append(browse);
  }
  function summary(container) {
    container.append(node('p', 'Your campus profile is ready. You can change it in settings any time.'));
    const course = courses.items.find(c => c.id === profile.course_id);
    container.append(node('p', `${course?.name || 'Course not selected'} · Class of ${profile.graduation_year || '—'}`, 'onboarding-summary'),
      node('p', `${profile.interest_ids.length} interests selected`));
    const followed = societies.items.filter(s => profile.followed_society_ids.includes(s.id));
    container.append(node('h3', `Following ${followed.length} societies`));
    const list = document.createElement('ul'); followed.forEach(s => list.append(node('li', s.name))); container.append(list);
    if (!followed.length) container.append(node('p', 'You can follow societies later.'));
  }
  function render() {
    el('ob-error').textContent = ''; el('ob-status').textContent = '';
    el('ob-step').textContent = `Step ${step} of 4`; el('ob-heading').textContent = names[step - 1];
    el('ob-progress').style.width = `${step * 25}%`;
    el('ob-back').hidden = step === 1;
    el('ob-next').textContent = step === 4 ? 'Explore events' : 'Save & continue';
    const container = el('ob-content'); container.replaceChildren();
    [about, interests, societyStep, summary][step - 1](container);
    el('ob-heading').focus();
  }
  async function save(nextStep, complete = false) {
    const {event_categories, ...data} = profile;
    profile = await workflowApi('/profile', {method: 'PUT', body: JSON.stringify({...data, step: nextStep, onboarding_completed: complete || profile.onboarding_completed})});
  }
  el('ob-next').addEventListener('click', async () => {
    if (busy || !profile) return;
    collectAbout();
    if (step === 1 && (!profile.course_id || !profile.graduation_year)) { el('ob-error').textContent = 'Choose your course and graduation year to continue.'; return; }
    setBusy(true); el('ob-status').textContent = 'Saving your preferences…';
    try {
      await save(Math.min(step + 1, 4), step === 4);
      if (step === 4) { view.hidden = true; await startWorkflow(); return; }
      if (step === 2) matches = await workflowApi('/societies/matches');
      step++; render();
    } catch (error) { el('ob-error').textContent = error.message; el('ob-status').textContent = 'Your selections are still here. Try again.'; }
    finally { setBusy(false); }
  });
  el('ob-back').addEventListener('click', () => { if (busy) return; collectAbout(); step = Math.max(1, step - 1); render(); });
  el('ob-signout').addEventListener('click', () => { ++sequence; profile = null; view.hidden = true; el('logout').click(); });

  async function openIfNeeded(state, edit = false) {
    if (state.user.role !== 'student' || (state.onboarding_completed && !edit)) return false;
    const version = ++sequence;
    el('app-view').hidden = true; el('login-view').hidden = true; view.hidden = false;
    el('ob-heading').textContent = 'Finding your corner of campus…'; el('ob-content').replaceChildren();
    el('ob-error').textContent = ''; el('ob-status').textContent = 'Loading your profile'; setBusy(true);
    try {
      const result = await Promise.all(['/profile','/courses','/interests','/societies'].map(path => workflowApi(path)));
      if (version !== sequence) return true;
      [profile, courses, groups, societies] = result; step = edit ? 1 : profile.step;
      matches = step >= 3 ? await workflowApi('/societies/matches') : [];
      render();
    } catch (error) {
      profile = null; el('ob-error').textContent = error.message; el('ob-status').textContent = '';
      const retry = node('button', 'Retry loading profile', 'interest-chip'); retry.type = 'button'; retry.onclick = () => openIfNeeded(state, edit); el('ob-content').append(retry);
    } finally { if (version === sequence) setBusy(false); }
    return true;
  }
  const edit = node('button', 'Edit your campus profile →', 'dummy-button'); edit.id = 'edit-student-profile'; edit.hidden = true;
  el('settings-panel').insertBefore(edit, el('logout'));
  edit.addEventListener('click', () => openIfNeeded({user: {role: 'student'}}, true));
  return {openIfNeeded, configure: state => { edit.hidden = state.user.role !== 'student'; }};
})();

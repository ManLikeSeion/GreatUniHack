const $ = (id) => document.getElementById(id);
let month = new Date();
month.setDate(1);
let selected = new Date();
let dayOpen = false;
let savedEvents = [];
try { const stored = JSON.parse(localStorage.getItem('common-events') || '[]'); if (Array.isArray(stored)) savedEvents = stored.filter(e => e && typeof e.date === 'string' && typeof e.time === 'string' && typeof e.title === 'string'); } catch {}
const dateKey = date => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
const categoryImages = { social: 'photo-1511795409834-ef04bbd61622', sports: 'photo-1546519638-68e109498ffc', culture: 'photo-1514525253161-7a46d19cd819', arts: 'photo-1513364776144-60967b0f800f', academic: 'photo-1497366811353-6870744d04b2', other: 'photo-1523580494863-6f3031224c94' };
function bannerImage(category) { return `https://images.unsplash.com/${categoryImages[category] || categoryImages.other}?auto=format&fit=crop&w=1000&q=80`; }
function samplesFor(date) {
 if (!sampleDays.includes(date.getDate())) return [];
 return [{ title: 'a little social, a lot of good company.', society: 'film society', time: '18:00', duration: 120, location: 'the copper rooms', category: 'social', description: 'meet fellow film lovers, swap recommendations and get to know your society. everyone is welcome.' }, { title: 'give badminton a go.', society: 'badminton society', time: '19:30', duration: 90, location: 'sports & wellness hub', category: 'sports', description: 'a relaxed evening on court for all abilities. bring trainers and a water bottle; we will bring the rackets.' }].map((event, index) => ({...event, id: `sample-${dateKey(date)}-${index}`, date: dateKey(date), sample: true}));
}
function eventId(event) { return event.id || JSON.stringify([event.date,event.time,event.title,event.society,event.owner]); }
function eventsFor(date) {
 return [...samplesFor(date), ...savedEvents.filter(e => e.date === dateKey(date))].sort((a,b) => a.time.localeCompare(b.time));
}
let preferences = { liked: [], signed: [] };
function loadPreferences() {
 preferences = { liked: [], signed: [] };
 try { const stored = JSON.parse(localStorage.getItem('common-plans:' + $('account-email').value.toLowerCase()) || '{}'); for (const key of ['liked','signed']) if (Array.isArray(stored[key])) preferences[key] = stored[key].filter(id => typeof id === 'string'); } catch {}
}
function isPlanned(event) { const id = eventId(event); return preferences.liked.includes(id) || preferences.signed.includes(id); }
function allEvents() {
 const start = new Date(); start.setHours(0,0,0,0);
 const samples = [];
 for (let offset=0;offset<45;offset++) { const day = new Date(start); day.setDate(day.getDate()+offset); samples.push(...samplesFor(day)); }
 return [...samples,...savedEvents].sort((a,b) => (a.date+a.time).localeCompare(b.date+b.time));
}
function changePlan(event, kind) {
 const id = eventId(event);
 const next = { ...preferences, [kind]: preferences[kind].includes(id) ? preferences[kind].filter(value => value !== id) : [...preferences[kind],id] };
 try { localStorage.setItem('common-plans:' + $('account-email').value.toLowerCase(), JSON.stringify(next)); } catch { notify('could not save your plans. browser storage is unavailable.'); return; }
 preferences = next;
 renderCalendar();
 // Update in place so liking does not reset the scroll position.
 document.querySelectorAll('[data-event-id]').forEach(row => {
  const item = allEvents().find(candidate => eventId(candidate) === row.dataset.eventId);
  if (!item) return;
  const actions = row.querySelector('.event-actions'); if (actions) actions.replaceChildren(...planButtons(item));
  const warning = row.querySelector('.clash-copy'); if (warning) warning.textContent = clashText(item);
  const graphic = row.querySelector('.clash-graphic'); if (graphic) updateClashGraphic(graphic, item);
  if (row.className === 'feed-event') row.hidden = !matchesDiscoverFilters(item);
 });
 updateFeedEmpty();
}
function notify(message) { $('toast').textContent=message; $('toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(() => $('toast').hidden=true,3500); }
function planButtons(event) {
 return [['liked','like + save','liked'],['signed','sign up','signed up']].map(([kind,label,active]) => {
  const button = document.createElement('button'); const on = preferences[kind].includes(eventId(event)); button.className='plan-button' + (on ? ' is-on' : ''); button.textContent = (kind === 'liked' ? (on ? '\u2665 ' : '\u2661 ') : (on ? '\u2713 ' : '+ ')) + (on ? active : label); button.setAttribute('aria-pressed',String(on)); button.addEventListener('click',()=>changePlan(event,kind)); return button;
 });
}
function minutes(event) { const [hours, mins] = event.time.split(':').map(Number); const [y,m,d]=event.date.split('-').map(Number); return new Date(y,m-1,d,hours,mins).getTime()/60000; }
function duration(event) { return Number(event.duration) > 0 ? Number(event.duration) : 60; }
function clashesFor(event) {
 const start = minutes(event), end = start + duration(event);
 const dates = [new Date(start*60000-86400000),new Date(start*60000),new Date(end*60000)];
 const candidates = new Map(dates.flatMap(date => eventsFor(date)).map(item => [eventId(item),item]));
 const clashes = [...candidates.values()].filter(other => eventId(other)!==eventId(event) && isPlanned(other) && start < minutes(other)+duration(other) && minutes(other) < end);
 return clashes;
}
function clashText(event) {
 const clashes = clashesFor(event);
 return clashes.length ? 'potential clash with ' + clashes.map(other => `${other.title} (${other.time})`).join(', ') : 'no clashes with your current plans.';
}
// Only animate a clash while its graphic is actually visible in the feed.
let clashObserver;
function observeClash(graphic) {
 if (typeof IntersectionObserver === 'undefined') return;
 if (!clashObserver) clashObserver = new IntersectionObserver(entries => {
  entries.forEach(entry => entry.target.classList.toggle('is-clanging', entry.isIntersecting && entry.intersectionRatio >= 0.6));
 }, { root: $('discover-feed'), threshold: [0, 0.6] });
 clashObserver.observe(graphic);
}
function updateClashGraphic(graphic, event) {
 if (clashObserver) clashObserver.unobserve(graphic);
 graphic.classList.remove('is-clanging');
 graphic.replaceChildren();
 const clash = clashesFor(event)[0];
 graphic.hidden = !clash;
 if (!clash) return;
 graphic.setAttribute('role', 'img');
 graphic.setAttribute('aria-label', `overlapping events: ${event.title} at ${event.time} and ${clash.title} at ${clash.time}`);
 const track = document.createElement('div'); track.className = 'clash-track'; track.setAttribute('aria-hidden', 'true');
 const chronological = [event, clash].sort((a, b) => minutes(a) - minutes(b) || eventId(a).localeCompare(eventId(b)));
 for (const [index, item] of chronological.entries()) {
  const name = index === 0 ? 'first' : 'second';
  const block = document.createElement('div'); block.className = `clash-block clash-${name}`;
  const time = document.createElement('span'); time.className = 'clash-time'; time.textContent = item.time;
  const label = document.createElement('strong'); label.textContent = item.title;
  block.append(time, label); track.append(block);
 }
 const spark = document.createElement('span'); spark.className = 'clash-spark';
 // A small four-point white spark, drawn locally so no image is needed.
 spark.innerHTML = '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 1 20 12 31 16 20 20 16 31 12 20 1 16 12 12Z"/><path d="m4 3 3 5m18 16 4 4M28 3l-4 5"/></svg>';
 track.append(spark); graphic.append(track); observeClash(graphic);
}
function eventCard(event, feed=false) {
 const card=document.createElement('article'); card.className=feed?'feed-event':'event-banner'; card.dataset.eventId=eventId(event);
 const visual=document.createElement('div'); visual.className=feed?'feed-visual':'banner-visual';
 const image=document.createElement('img'); image.alt=''; image.loading='lazy'; image.src=typeof event.image==='string' && event.image.startsWith('https://')?event.image:bannerImage(event.category); image.addEventListener('error',()=>image.remove()); visual.append(image);
 const content=document.createElement('div'); content.className='banner-content';
 for(const [tag,text,name] of [['span',`${event.category} ? ${event.sample?'sample event':event.society}`,'event-category'],['p',`${event.date} ? ${event.time} ? ${duration(event)} min`,'event-meta'],['h3',event.title,''],['p',event.description,'event-description'],['span',event.society,'event-society']]) { const node=document.createElement(tag); node.textContent=text; node.className=name; content.append(node); }
 visual.append(content);
 const actions=document.createElement('div'); actions.className='event-actions'; actions.append(...planButtons(event));
 if(feed) {
  const details=document.createElement('div');details.className='feed-details';
  const heading=document.createElement('h2');heading.textContent='the little details.';
  const place=document.createElement('p');place.textContent=event.location;
  const hint=document.createElement('p');hint.className='field-note';hint.textContent='like to save to your calendar. sign up to mark yourself as going. demo sign-ups stay on this device.';
  details.append(heading,place,actions,hint);
  const plans=document.createElement('div');plans.className='feed-plans';const title=document.createElement('h2');title.textContent='room in your day?';const warning=document.createElement('p');warning.className='clash-copy';warning.textContent=clashText(event);const note=document.createElement('p');note.className='field-note';note.textContent='checked against liked and signed-up events. older events use a 60 minute duration.';const graphic=document.createElement('div');graphic.className='clash-graphic';updateClashGraphic(graphic,event);plans.append(title,graphic,warning,note);
  card.append(details,visual,plans);
 } else {card.append(visual,actions);}
 return card;
}
function matchesDiscoverFilters(event) {
 const status = $('feed-filter').value || 'all';
 const category = $('discover-category').value || 'all';
 const date = $('discover-date').value;
 const query = $('discover-search').value.trim().toLowerCase();
 return (status === 'all' || preferences[status].includes(eventId(event)))
  && (category === 'all' || event.category === category)
  && (!date || event.date === date)
  && (!query || [event.title,event.society,event.location,event.description,event.category].join(' ').toLowerCase().includes(query))
  && (!$('discover-no-clashes').checked || clashesFor(event).length === 0);
}
function updateFeedEmpty() {
 const rows=[...$('discover-feed').children].filter(row=>row.dataset.eventId);
 const count=rows.filter(row=>!row.hidden).length;
 $('feed-empty').hidden=count>0;
 $('discover-count').textContent=`${count} ${count===1?'event':'events'} to explore`;
}
function renderFeed() {
 if (clashObserver) clashObserver.disconnect();
 const feed=$('discover-feed');feed.replaceChildren();
 for(const event of allEvents()) { const card=eventCard(event,true);card.hidden=!matchesDiscoverFilters(event);feed.append(card); }
 const empty=document.createElement('p');empty.id='feed-empty';empty.className='feed-empty';empty.textContent='no events match these filters. try another date or clear your filters.';feed.append(empty);updateFeedEmpty();
 feed.scrollTop=0;
}
function applyDiscoverFilters() {
 // Keep all cards available so liking or signing up can update filter results in place.
 const feed=$('discover-feed');
 const existing=new Map([...feed.children].filter(row=>row.dataset.eventId).map(row=>[row.dataset.eventId,row]));
 for(const event of allEvents()) {
  let card=existing.get(eventId(event));
  if(!card) {card=eventCard(event,true);feed.insertBefore(card,$('feed-empty'));}
  card.hidden=!matchesDiscoverFilters(event);
 }
 updateFeedEmpty();feed.scrollTop=0;
}
const icons = '<span class="event-dot"></span>';
const sampleDays = [4, 7, 10, 12, 17, 20, 24, 27];
let loginRole = null;
let accountRole = 'student';
const roleTabs = { student: ['discover','calendar','settings'], exec: ['discover','calendar','create','settings'], external: ['promote','settings'] };
function chooseRole(role) {
 if (!roleTabs[role]) return;
 loginRole = role;
 document.querySelectorAll('[data-role]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.role === role)));
 $('login-form').hidden = false;
 $('role-summary').textContent = `signing in as ${role}`;
 $('email').placeholder = role === 'external' ? 'you@your-business.com' : 'you@warwick.ac.uk';
 $('email').focus();
}
document.querySelectorAll('[data-role]').forEach(button => button.addEventListener('click',()=>chooseRole(button.dataset.role)));
$('change-role').addEventListener('click',()=>{loginRole=null;$('login-form').hidden=true;document.querySelectorAll('[data-role]').forEach(button=>button.setAttribute('aria-pressed','false'));});
function showApp(email, role = 'student') {
  accountRole = roleTabs[role] ? role : 'student';
  currentTab = null;
  document.querySelectorAll('[data-tab]').forEach(button => button.hidden = !roleTabs[accountRole].includes(button.dataset.tab));
  $('account-role').textContent = `${accountRole} account ? demo role, not verified`;

  $('login-view').hidden = true;
  $('app-view').hidden = false;
  $('account-email').value = email;
  renderPromotions();
  loadPreferences();
  setTab(accountRole === 'external' ? 'promote' : 'discover');
  renderCalendar();
}
$('login-form').addEventListener('submit', (event) => {
  event.preventDefault();
  if (!loginRole) return;
  const email = $('email').value.trim();
  if (!$('email').checkValidity()) return $('email').reportValidity();
  try { sessionStorage.setItem('common-email', email); sessionStorage.setItem('common-role', loginRole); } catch {}
  showApp(email, loginRole);
});
function renderCalendar() {
  $('month-label').textContent = month.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' }).toLowerCase();
  const offset = (month.getDay() + 6) % 7;
  const length = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const grid = $('calendar-grid');
  grid.replaceChildren();
  for (let i = 0; i < Math.ceil((offset + length) / 7) * 7; i++) {
    const date = new Date(month.getFullYear(), month.getMonth(), i - offset + 1);
    const current = date.getMonth() === month.getMonth();
    const button = document.createElement('button');
    button.className = 'day' + (!current ? ' other-month' : '') + (date.toDateString() === selected.toDateString() ? ' selected' : '') + (date.toDateString() === new Date().toDateString() ? ' is-today' : '');
    button.setAttribute('aria-label', date.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).toLowerCase());
    button.setAttribute('aria-pressed', String(date.toDateString() === selected.toDateString()));
    button.innerHTML = `<span>${date.getDate()}</span>${eventsFor(date).some(event => !$('personal-only').checked || isPlanned(event)) ? icons : '<span style="height:5px"></span>'}`;
    button.addEventListener('click', () => { selected = date; dayOpen = true; if (!current) month = new Date(date.getFullYear(), date.getMonth(), 1); renderCalendar(); });
    grid.append(button);
  }
  $('selected-date').textContent = selected.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'short' }).toLowerCase();
  $('calendar-panel').classList.toggle('day-open', dayOpen);
  $('day-menu').hidden = !dayOpen;
  const list = $('event-list');
  list.replaceChildren();
  const events = eventsFor(selected).filter(event => !$('personal-only').checked || isPlanned(event));
  if (!events.length) {
    const empty = document.createElement('p'); empty.className = 'empty-events'; empty.textContent = 'a little breathing room. no events for this day yet.'; list.append(empty);
    const create = document.createElement('button'); create.hidden = accountRole !== 'exec'; create.className = 'dummy-button'; create.textContent = 'be the first to make a plan +'; create.addEventListener('click', () => { setTab('create'); $('event-date').value = dateKey(selected); }); list.append(create);
  }
  for (const [key, title] of [['signed','you are going.'],['liked','your favourites.'],['other','on your radar.']]) {
    const section=document.createElement('section'); section.className='agenda-group';
    const items=events.filter(event => key==='signed'?preferences.signed.includes(eventId(event)):key==='liked'?preferences.liked.includes(eventId(event))&&!preferences.signed.includes(eventId(event)):!isPlanned(event));
    const heading=document.createElement('h3');heading.className='agenda-heading';heading.textContent=`${title} (${items.length})`;section.append(heading);
    if(!items.length) {const empty=document.createElement('p');empty.className='field-note';empty.textContent=key==='signed'?'no sign-ups for this day yet.':key==='liked'?'no favourites for this day yet.':'you are all caught up.';section.append(empty);}
    items.forEach(event=>section.append(eventCard(event)));list.append(section);
  }
}
for (const [id, change] of [['previous-month', -1], ['next-month', 1]]) $(id).addEventListener('click', () => { month.setMonth(month.getMonth() + change); renderCalendar(); });
$('today').addEventListener('click', () => { selected = new Date(); dayOpen = true; month = new Date(selected.getFullYear(), selected.getMonth(), 1); renderCalendar(); });
const tabOrder = ['discover', 'calendar', 'create', 'promote', 'settings'];
let currentTab = null;
let tabTransition = 0;
let runningTabAnimations = [];
function setTab(tab) {
  if (!roleTabs[accountRole].includes(tab)) return;
  const previous = currentTab;
  const version = ++tabTransition;
  runningTabAnimations.forEach(animation => animation.cancel());
  runningTabAnimations = [];
  const outgoing = previous ? $(previous + '-panel') : null;
  const incoming = $(tab + '-panel');
  const visibleTabs = roleTabs[accountRole];
  const distance = visibleTabs.indexOf(tab) - visibleTabs.indexOf(previous);
  const slide = Math.abs(distance) === 1;
  const direction = Math.sign(distance);
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.querySelectorAll('[data-tab]').forEach(button => {
    const active = button.dataset.tab === tab;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  function reveal() {
    if (version !== tabTransition) return;
    const moveFocus = outgoing && outgoing.contains(document.activeElement);
    tabOrder.forEach(name => { const panel = $(name + '-panel'); panel.hidden = name !== tab; panel.inert = name !== tab; });
    currentTab = tab;
    $('page-title').textContent = { promote: 'give your business a little spotlight.', discover: 'find your next good plan.', calendar: 'make room for good plans.', settings: 'a space that feels like you.', create: 'bring your people together.' }[tab];
    if (tab === 'discover') renderFeed();
    if (moveFocus) { incoming.tabIndex = -1; incoming.focus({ preventScroll: true }); }
    if (!previous || previous === tab || reducedMotion || typeof incoming.animate !== 'function') return;
    const animation = incoming.animate([
      { opacity: 0, transform: slide ? `translateX(${direction * 42}px)` : 'none' },
      { opacity: 1, transform: 'translateX(0)' }
    ], { duration: slide ? 220 : 180, easing: 'cubic-bezier(.22,.61,.36,1)' });
    runningTabAnimations.push(animation);
  }
  if (!outgoing || previous === tab || reducedMotion || $('app-view').hidden || typeof outgoing.animate !== 'function') { reveal(); return; }
  outgoing.inert = true;
  const animation = outgoing.animate([
    { opacity: 1, transform: 'translateX(0)' },
    { opacity: 0, transform: slide ? `translateX(${-direction * 42}px)` : 'none' }
  ], { duration: slide ? 140 : 160, easing: 'ease-in', fill: 'forwards' });
  runningTabAnimations.push(animation);
  animation.finished.then(() => { if (version === tabTransition) { reveal(); animation.cancel(); } }).catch(() => {});
}

document.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', () => setTab(button.dataset.tab)));
let toastTimer;
document.querySelectorAll('[data-message]').forEach(button => button.addEventListener('click', () => { $('toast').textContent = button.dataset.message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 3000); }));
$('logout').addEventListener('click', () => {
 try { sessionStorage.removeItem('common-email'); sessionStorage.removeItem('common-role'); } catch {}
 ++tabTransition;runningTabAnimations.forEach(animation=>animation.cancel());runningTabAnimations=[];currentTab=null;
 $('app-view').hidden=true;$('login-view').hidden=false;$('email').value='';loginRole=null;$('login-form').hidden=true;
 document.querySelectorAll('[data-role]').forEach(button=>button.setAttribute('aria-pressed','false'));
 $('promotion-form').reset();$('promotion-review').hidden=true;pendingPromotion=null;$('promotion-status').textContent='';
});


$('close-day').addEventListener('click', () => { dayOpen = false; renderCalendar(); });
$('event-image').addEventListener('input', () => $('event-image').setCustomValidity(''));
$('event-form').addEventListener('submit', event => {
  event.preventDefault();
  if (accountRole !== 'exec') return;
  const image = $('event-image').value.trim();
  if (image && !image.startsWith('https://')) { $('event-image').setCustomValidity('please use an https image link.'); $('event-image').reportValidity(); return; }
  const fields = ['title', 'society', 'category', 'date', 'time', 'location', 'description'];
  const created = Object.fromEntries(fields.map(key => [key, $('event-' + key).value.trim()]));
  for (const key of fields) { if (!created[key]) { $('event-' + key).focus(); return; } }
  created.image = image;
  created.id = crypto.randomUUID();
  created.duration = Number($('event-duration').value);
  if (!Number.isFinite(created.duration) || created.duration < 15 || created.duration > 1440) return;
  created.owner = $('account-email').value;
  const next = [...savedEvents, created];
  try { localStorage.setItem('common-events', JSON.stringify(next)); } catch { $('save-error').hidden = false; $('save-error').textContent = 'could not save this event. browser storage may be full or unavailable. please try again.'; return; }
  savedEvents = next;
  const [year, monthIndex, day] = created.date.split('-').map(Number);
  selected = new Date(year, monthIndex - 1, day); month = new Date(year, monthIndex - 1, 1); dayOpen = true;
  $('event-form').reset(); $('save-error').hidden = true; setTab('calendar'); renderCalendar();
  $('toast').textContent = 'your event is on the calendar.'; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 3500);
});

$('feed-filter').addEventListener('change',applyDiscoverFilters);
$('discover-filters').addEventListener('submit', event => event.preventDefault());
$('discover-search').addEventListener('input',applyDiscoverFilters);
for(const id of ['discover-category','discover-date','discover-no-clashes']) $(id).addEventListener('change',applyDiscoverFilters);
$('clear-discover-filters').addEventListener('click',()=>{ $('discover-filters').reset(); $('feed-filter').value='all'; applyDiscoverFilters(); });
$('personal-only').addEventListener('change',renderCalendar);


let pendingPromotion = null;
const promotionKey = () => 'common-promotions:' + $('account-email').value.toLowerCase();
function renderPromotions() {
 const list=$('promotion-list');list.replaceChildren();
 let promotions=[];try {const stored=JSON.parse(localStorage.getItem(promotionKey()) || '[]');if(Array.isArray(stored)) promotions=stored;}catch{}
 if(!promotions.length){const empty=document.createElement('p');empty.className='field-note';empty.textContent='your first promotion starts here.';list.append(empty);}
 promotions.forEach(promo=>{const item=document.createElement('p');item.className='organiser-note';item.textContent=`${promo.title} ? ${promo.date} ? ${promo.days} days ? ?${promo.total} ? simulated payment, not published`;list.append(item);});
}
$('promo-days').addEventListener('change',()=>{$('promo-total').textContent='?'+Number($('promo-days').value)*15;});
$('promotion-form').addEventListener('input',()=>{$('promotion-review').hidden=true;pendingPromotion=null;$('promotion-status').textContent='';});
$('promotion-form').addEventListener('submit',event=>{
 event.preventDefault();if(accountRole!=='external')return;
 const values=Object.fromEntries(['business','title','description','link','date','days'].map(key=>[key,$('promo-'+key).value.trim()]));
 if(Object.values(values).some(value=>!value))return;
 try { if(new URL(values.link).protocol!=='https:') {notify('please use an https website link.');return;} } catch {return;}
 if(values.date<dateKey(new Date())) {notify('choose today or a future date.');return;}
 if(![1,3,7].includes(Number(values.days)))return;
 pendingPromotion={...values,total:Number(values.days)*15};
 $('promo-preview').textContent=`${values.business} ? ${values.title} ? starts ${values.date} ? ${values.days} days ? ?${pendingPromotion.total}`;
 $('promotion-review').hidden=false;
});
$('demo-payment').addEventListener('click',()=>{
 if(accountRole!=='external'||!pendingPromotion)return;
 try {const stored=JSON.parse(localStorage.getItem(promotionKey())||'[]');localStorage.setItem(promotionKey(),JSON.stringify([...(Array.isArray(stored)?stored:[]),pendingPromotion]));}
 catch {$('promotion-status').textContent='could not save your demo promotion. browser storage may be unavailable.';return;}
 pendingPromotion=null;$('promotion-review').hidden=true;$('promotion-form').reset();$('promo-total').textContent='?45';$('promotion-status').textContent='demo payment complete. no charge was made and your promotion is not published.';renderPromotions();
});
try { const email=sessionStorage.getItem('common-email'); if(email) showApp(email,sessionStorage.getItem('common-role')||'student'); } catch {}

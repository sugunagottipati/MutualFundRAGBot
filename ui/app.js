const form = document.querySelector('#ask-form');
const queryInput = document.querySelector('#query');
const sendButton = document.querySelector('#send-button');
const chat = document.querySelector('#chat');
const drawer = document.querySelector('#source-drawer');
const backdrop = document.querySelector('#drawer-backdrop');
const sourceList = document.querySelector('#source-list');
const toast = document.querySelector('#toast');

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('is-visible');
  window.setTimeout(() => toast.classList.remove('is-visible'), 2600);
}

function addUserMessage(text) {
  const message = document.createElement('div');
  message.className = 'user-message';
  message.textContent = text;
  chat.append(message);
}

function addLoading() {
  const loading = document.createElement('div');
  loading.className = 'assistant-message loading-message';
  loading.innerHTML = '<span class="message-mark">F</span><div><p class="message-meta">FundFacts <time>Now</time></p><p class="loading">Checking approved sources… <i></i><i></i><i></i></p></div>';
  chat.append(loading);
  chat.scrollTop = chat.scrollHeight;
  return loading;
}

function addAnswer(response) {
  const wrapper = document.createElement('div');
  wrapper.className = 'assistant-message';
  const body = document.createElement('div');
  body.className = 'answer-card';
  const label = document.createElement('div');
  label.className = 'answer-card__label';
  label.textContent = response.route === 'factual' ? 'Verified factual answer' : 'Facts-only guidance';
  const answer = document.createElement('p');
  answer.textContent = response.answer;
  const footer = document.createElement('div');
  footer.className = 'answer-card__footer';
  const citation = document.createElement('a');
  citation.href = response.citation;
  citation.target = '_blank';
  citation.rel = 'noopener noreferrer';
  citation.textContent = 'View verified source ↗';
  const updated = document.createElement('span');
  updated.textContent = `Last updated from sources: ${response.last_updated_from_sources}`;
  const copy = document.createElement('button');
  copy.className = 'copy-link';
  copy.type = 'button';
  copy.textContent = 'Copy answer';
  copy.addEventListener('click', async () => {
    await navigator.clipboard.writeText(response.answer);
    showToast('Answer copied');
  });
  footer.append(citation, updated, copy);
  body.append(label, answer, footer);
  wrapper.append(Object.assign(document.createElement('span'), { className: 'message-mark', textContent: 'F' }), body);
  chat.append(wrapper);
}

async function ask(query) {
  addUserMessage(query);
  const loading = addLoading();
  sendButton.disabled = true;
  queryInput.disabled = true;
  try {
    const response = await fetch('/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query }) });
    if (!response.ok) throw new Error('Assistant unavailable');
    addAnswer(await response.json());
  } catch (error) {
    const message = document.createElement('div');
    message.className = 'assistant-message';
    message.innerHTML = '<span class="message-mark">F</span><div class="answer-card"><div class="answer-card__label">Temporarily unavailable</div><p>We could not reach the assistant. Please try again shortly.</p></div>';
    chat.append(message);
  } finally {
    loading.remove();
    sendButton.disabled = false;
    queryInput.disabled = false;
    queryInput.focus();
    chat.scrollTop = chat.scrollHeight;
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (!query || sendButton.disabled) return;
  queryInput.value = '';
  queryInput.style.height = 'auto';
  ask(query);
});

queryInput.addEventListener('input', () => {
  queryInput.style.height = 'auto';
  queryInput.style.height = `${Math.min(queryInput.scrollHeight, 110)}px`;
});
queryInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
document.querySelectorAll('.example').forEach((button) => button.addEventListener('click', () => {
  queryInput.value = button.dataset.query;
  form.requestSubmit();
}));

function setDrawer(open) {
  drawer.classList.toggle('is-open', open);
  drawer.setAttribute('aria-hidden', String(!open));
  backdrop.hidden = !open;
  if (open) document.querySelector('#close-sources').focus();
}

document.querySelector('#open-sources').addEventListener('click', async () => {
  setDrawer(true);
  try {
    const response = await fetch('/sources');
    if (!response.ok) throw new Error('Source list unavailable');
    const payload = await response.json();
    sourceList.replaceChildren(...payload.sources.map((source) => {
      const item = document.createElement('div');
      item.className = 'source-item';
      const name = source.source_url.split('/').pop().replace(/-/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
      item.innerHTML = `<strong>${name}</strong><a href="${source.source_url}" target="_blank" rel="noopener noreferrer">${source.source_url}</a><small>Approved source · Verified</small>`;
      return item;
    }));
    document.querySelector('#source-count').textContent = payload.sources.length;
  } catch (error) {
    sourceList.innerHTML = '<p class="muted">The approved source list is temporarily unavailable.</p>';
  }
});
document.querySelector('#close-sources').addEventListener('click', () => setDrawer(false));
backdrop.addEventListener('click', () => setDrawer(false));
document.addEventListener('keydown', (event) => { if (event.key === 'Escape') setDrawer(false); });
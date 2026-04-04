const state = {
  profile: { xp: 0, hearts: 5, streak_days: 0, badges: [], completed_lessons: [], streak_freezes: 0 },
  path: [],
  currentLesson: null,
  sessionId: null,
  quizIndex: 0,
  selectedOption: null,
  correctCount: 0,
  claimInFlight: false,
};

const ui = {
  xpValue: document.getElementById('xpValue'),
  streakValue: document.getElementById('streakValue'),
  heartValue: document.getElementById('heartValue'),
  badgeValue: document.getElementById('badgeValue'),
  freezeOwned: document.getElementById('freezeOwned'),
  claimReward: document.getElementById('claimReward'),
  buyFreezeOne: document.getElementById('buyFreezeOne'),
  buyFreezeTwo: document.getElementById('buyFreezeTwo'),
  leagueTier: document.getElementById('leagueTier'),
  leagueProgressBar: document.getElementById('leagueProgressBar'),
  leagueHint: document.getElementById('leagueHint'),
  rewardToast: document.getElementById('rewardToast'),
  rewardTitle: document.getElementById('rewardTitle'),
  rewardText: document.getElementById('rewardText'),
  questList: document.getElementById('questList'),
  badgeList: document.getElementById('badgeList'),
  pathContainer: document.getElementById('pathContainer'),
  refreshPath: document.getElementById('refreshPath'),
  lessonModal: document.getElementById('lessonModal'),
  closeLesson: document.getElementById('closeLesson'),
  lessonTitle: document.getElementById('lessonTitle'),
  lessonIntro: document.getElementById('lessonIntro'),
  quizBox: document.getElementById('quizBox'),
  quizPrompt: document.getElementById('quizPrompt'),
  quizStage: document.getElementById('quizStage'),
  videoCountdown: document.getElementById('videoCountdown'),
  videoHint: document.getElementById('videoHint'),
  quizVideo: document.getElementById('quizVideo'),
  quizOptionsWrap: document.getElementById('quizOptionsWrap'),
  quizOptions: document.getElementById('quizOptions'),
  submitAnswer: document.getElementById('submitAnswer'),
  nextQuestion: document.getElementById('nextQuestion'),
  quizFeedback: document.getElementById('quizFeedback'),
  startLesson: document.getElementById('startLesson'),
  finishLesson: document.getElementById('finishLesson'),
  lessonDialog: document.getElementById('lessonDialog'),
  lessonSummary: document.getElementById('lessonSummary'),
  summaryStats: document.getElementById('summaryStats'),
  summaryInsights: document.getElementById('summaryInsights'),
};

const VIDEO_PLAYBACK_LOOPS = 2;
const COUNTDOWN_SECONDS = 3;

async function getJSON(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function renderProfile() {
  ui.xpValue.textContent = state.profile.xp;
  ui.streakValue.textContent = `${state.profile.streak_days} days`;
  ui.heartValue.textContent = state.profile.hearts;
  ui.badgeValue.textContent = state.profile.badges.length;
  ui.freezeOwned.textContent = state.profile.streak_freezes || 0;

  ui.badgeList.innerHTML = '';
  const recent = state.profile.badges.slice(-5);
  if (!recent.length) {
    const li = document.createElement('li');
    li.textContent = 'Complete lessons to unlock milestones.';
    ui.badgeList.appendChild(li);
    return;
  }
  recent.forEach((badge) => {
    const li = document.createElement('li');
    li.textContent = badge;
    ui.badgeList.appendChild(li);
  });

  syncClaimButtonFromState();
  renderLeagueCard();
}

function syncLearningThemeWithGlobal() {
  const globalTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  document.body.classList.remove('light', 'dark');
  document.body.classList.add(globalTheme);
}

function initLearningThemeSync() {
  syncLearningThemeWithGlobal();
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'attributes' && mutation.attributeName === 'data-theme') {
        syncLearningThemeWithGlobal();
      }
    }
  });
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
}

function setClaimButtonState(isClaimed) {
  ui.claimReward.disabled = Boolean(isClaimed);
  ui.claimReward.textContent = isClaimed ? 'Already claimed today' : 'Claim Daily Practice Reward';
}

function syncClaimButtonFromState() {
  setClaimButtonState(Boolean(state.profile.reward_claimed_today));
}

function renderLessonSummary(result) {
  const stats = result.stats || {};
  const correct = stats.correct_answers ?? 0;
  const total = stats.total_questions ?? 0;
  const score = stats.score_percent ?? 0;
  const points = stats.points_scored ?? 0;
  const xp = stats.xp_awarded ?? 0;
  const coins = stats.coins_awarded ?? 0;
  const gems = stats.gems_awarded ?? 0;

  ui.summaryStats.textContent =
    `Correct ${correct}/${total} | Score ${score}% | Points ${points} | Expression Score +${xp} | Coins +${coins} | Gems +${gems}`;

  ui.summaryInsights.innerHTML = '';
  const tips = result.memory_suggestions || [];
  if (!tips.length) {
    const li = document.createElement('li');
    li.textContent = 'Great job. No incorrect answers this time.';
    ui.summaryInsights.appendChild(li);
  } else {
    tips.forEach((tip) => {
      const li = document.createElement('li');
      li.textContent = `${tip.correct_answer}: ${tip.suggestion}`;
      ui.summaryInsights.appendChild(li);
    });
  }

  ui.lessonSummary.classList.remove('hidden');
}

function renderLeagueCard() {
  const xp = state.profile.xp || 0;
  const tiers = [
    { name: 'Bronze League', min: 0, max: 400 },
    { name: 'Silver League', min: 401, max: 900 },
    { name: 'Gold League', min: 901, max: 1500 },
    { name: 'Diamond League', min: 1501, max: 99999 },
  ];

  const tier = tiers.find((item) => xp >= item.min && xp <= item.max) || tiers[0];
  const range = Math.max(1, tier.max - tier.min);
  const progress = Math.max(0, Math.min(100, Math.round(((xp - tier.min) / range) * 100)));

  ui.leagueTier.textContent = tier.name;
  ui.leagueProgressBar.style.width = `${progress}%`;

  const nextTier = tiers.find((item) => item.min > tier.min);
  if (nextTier) {
    const need = Math.max(0, nextTier.min - xp);
    ui.leagueHint.textContent = `Earn ${need} Expression Score to reach ${nextTier.name}.`;
  } else {
    ui.leagueHint.textContent = 'You are in the top league. Keep the momentum.';
  }
}

function renderQuests(quests) {
  ui.questList.innerHTML = '';
  quests.forEach((quest) => {
    const li = document.createElement('li');
    li.textContent = `${quest.title} (+${quest.reward_xp} Expression Score)`;
    ui.questList.appendChild(li);
  });
}

function lessonButtonClass(status) {
  if (status === 'completed') return 'completed';
  if (status === 'unlocked') return 'unlocked';
  return 'locked';
}

function normalizeLessonStatuses(lessons) {
  let unlockedAssigned = false;
  return lessons.map((lesson, index) => {
    if (lesson.status === 'completed') {
      return lesson;
    }

    if (!unlockedAssigned && (index === 0 || lessons[index - 1].status === 'completed')) {
      unlockedAssigned = true;
      return { ...lesson, status: 'unlocked' };
    }

    return { ...lesson, status: 'locked' };
  });
}

function flattenLessonTrackData() {
  const flat = [];
  state.path.forEach((level) => {
    (level.sublevels || []).forEach((sub) => {
      (sub.lessons || []).forEach((lesson, idx) => {
        let status = 'locked';
        if (lesson.completed) status = 'completed';
        else if (lesson.unlocked) status = 'unlocked';

        flat.push({
          id: lesson.lesson_id,
          label: lesson.label || `Lesson ${idx + 1}`,
          goal: lesson.goal || 'Build expressive hand communication.',
          section: sub.name || level.name || 'Learning',
          status,
        });
      });
    });
  });

  return normalizeLessonStatuses(flat);
}

function usageFromLesson(lesson, sublevelName) {
  if (lesson.goal) {
    return `Used in daily conversations: ${lesson.goal}.`;
  }
  return `Used in real-world ${String(sublevelName || '').toLowerCase()} interactions.`;
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function setQuizStageMode(mode) {
  ui.quizStage.classList.remove('is-preview', 'is-ready');
  if (mode) {
    ui.quizStage.classList.add(mode);
  }
}

function setOptionsState(stateName) {
  ui.quizOptionsWrap.classList.remove('hidden', 'is-blurred', 'is-visible');
  if (stateName === 'hidden') {
    ui.quizOptionsWrap.classList.add('hidden');
    return;
  }

  if (stateName === 'blurred') {
    ui.quizOptionsWrap.classList.add('is-blurred');
  }

  if (stateName === 'visible') {
    ui.quizOptionsWrap.classList.add('is-visible');
  }
}

function resetVideoState() {
  ui.quizVideo.pause();
  ui.quizVideo.currentTime = 0;
  ui.quizVideo.loop = false;
  ui.quizVideo.playbackRate = 1;
}

async function waitForVideoReady() {
  if (ui.quizVideo.readyState >= 2) {
    return;
  }

  await new Promise((resolve) => {
    const handleReady = () => resolve();
    ui.quizVideo.addEventListener('loadedmetadata', handleReady, { once: true });
    ui.quizVideo.addEventListener('loadeddata', handleReady, { once: true });
  });
}

async function playVideoTwice() {
  ui.quizVideo.currentTime = 0;
  ui.quizVideo.loop = false;
  ui.quizVideo.playbackRate = 1;

  for (let loopCount = 0; loopCount < VIDEO_PLAYBACK_LOOPS; loopCount += 1) {
    await new Promise((resolve) => {
      const handleEnded = () => resolve();
      ui.quizVideo.addEventListener('ended', handleEnded, { once: true });

      ui.quizVideo.currentTime = 0;
      const playResult = ui.quizVideo.play();
      if (playResult && typeof playResult.catch === 'function') {
        playResult.catch(() => {});
      }
    });

    if (loopCount < VIDEO_PLAYBACK_LOOPS - 1) {
      await sleep(140);
    }
  }
}

async function runQuestionIntroSequence() {
  if (!state.currentLesson) {
    return;
  }

  const questions = state.currentLesson.quiz.questions || [];
  const current = questions[state.quizIndex];
  if (!current) {
    ui.finishLesson.classList.remove('hidden');
    return;
  }

  setOptionsState('hidden');
  ui.submitAnswer.classList.add('hidden');
  ui.nextQuestion.classList.add('hidden');
  ui.finishLesson.classList.add('hidden');

  setQuizStageMode('is-preview');
  ui.videoCountdown.classList.remove('hidden');

  for (let count = COUNTDOWN_SECONDS; count >= 1; count -= 1) {
    ui.videoCountdown.textContent = count;
    await sleep(850);
  }

  ui.videoCountdown.classList.add('hidden');
  ui.quizStage.classList.remove('is-preview');
  ui.quizStage.classList.add('is-ready');

  await waitForVideoReady();
  resetVideoState();
  await playVideoTwice();

  ui.quizStage.classList.remove('is-ready');
  ui.lessonDialog.classList.add('is-blurred');
  await sleep(360);
  ui.lessonDialog.classList.remove('is-blurred');
  setOptionsState('visible');
  ui.submitAnswer.classList.remove('hidden');
}

function renderPath() {
  ui.pathContainer.innerHTML = '';
  const lessons = flattenLessonTrackData();
  if (!lessons.length) {
    ui.pathContainer.innerHTML = '<p>Path data unavailable.</p>';
    return;
  }

  const shell = document.createElement('div');
  shell.className = 'lesson-track-shell';

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.classList.add('lesson-track-svg');

  const basePath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  basePath.classList.add('track-path-base');

  const activePath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  activePath.classList.add('track-path-active');

  const flowPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  flowPath.classList.add('track-path-flow');

  const nodeLayer = document.createElement('div');
  nodeLayer.className = 'lesson-track-nodes';

  shell.appendChild(svg);
  shell.appendChild(nodeLayer);
  svg.appendChild(basePath);
  svg.appendChild(activePath);
  svg.appendChild(flowPath);
  ui.pathContainer.appendChild(shell);

  const width = Math.max(ui.pathContainer.clientWidth - 12, 320);
  const xCenter = width / 2;
  const swing = Math.min(108, Math.max(52, width * 0.16));
  const stepY = 140;
  const topPadding = 70;
  const points = lessons.map((_, idx) => ({
    x: xCenter + (Math.sin((idx * 0.95) + 0.45) * swing),
    y: topPadding + (idx * stepY),
  }));
  const height = points[points.length - 1].y + 82;

  shell.style.height = `${height + 22}px`;
  svg.setAttribute('viewBox', `0 0 ${width} ${height + 22}`);
  svg.setAttribute('preserveAspectRatio', 'none');

  const d = points.reduce((acc, point, idx) => {
    if (idx === 0) return `M ${point.x} ${point.y}`;
    const prev = points[idx - 1];
    const deltaX = point.x - prev.x;
    const cp1x = prev.x + (deltaX * 0.32);
    const cp1y = prev.y + (stepY * 0.4);
    const cp2x = prev.x + (deltaX * 0.68);
    const cp2y = point.y - (stepY * 0.4);
    return `${acc} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${point.x} ${point.y}`;
  }, '');

  basePath.setAttribute('d', d);
  activePath.setAttribute('d', d);
  flowPath.setAttribute('d', d);
  const pathLength = activePath.getTotalLength();
  let completedFromStart = 0;
  for (const lesson of lessons) {
    if (lesson.status === 'completed') completedFromStart += 1;
    else break;
  }
  const totalSegments = Math.max(1, lessons.length - 1);
  const progressRatio = Math.max(0, Math.min(1, completedFromStart / totalSegments));
  const activeLength = pathLength * progressRatio;
  activePath.style.strokeDasharray = `${pathLength}`;
  activePath.style.strokeDashoffset = `${pathLength}`;
  flowPath.style.strokeDasharray = '12 18';
  flowPath.style.strokeDashoffset = '0';
  requestAnimationFrame(() => {
    activePath.classList.add('draw');
    activePath.style.strokeDashoffset = `${Math.max(0, pathLength - activeLength)}`;
    flowPath.classList.add('draw');
  });

  const currentLesson = lessons.find((item) => item.status === 'unlocked');
  lessons.forEach((lesson, idx) => {
    const point = points[idx];
    const node = document.createElement('button');
    node.className = `path-node ${lessonButtonClass(lesson.status)}`;
    node.classList.add(`island-v${(idx % 4) + 1}`);
    node.style.left = `${point.x}px`;
    node.style.top = `${point.y}px`;
    node.title = lesson.goal;
    node.setAttribute('data-lesson-id', lesson.id);

    if (currentLesson && currentLesson.id === lesson.id) {
      node.classList.add('current-lesson');
    }

    const icon = document.createElement('span');
    icon.className = 'node-icon';
    icon.textContent = lesson.status === 'locked' ? '🔒' : '🤟';

    const label = document.createElement('span');
    label.className = 'node-label';
    label.textContent = lesson.label;

    const subtitle = document.createElement('span');
    subtitle.className = 'node-subtitle';
    subtitle.textContent = usageFromLesson({ goal: lesson.goal }, lesson.section);

    node.appendChild(icon);
    node.appendChild(label);
    node.appendChild(subtitle);
    if (lesson.status === 'completed') {
      const flag = document.createElement('span');
      flag.className = 'island-flag';
      flag.innerHTML = '<span class="flag-pole"></span><span class="flag-cloth"></span>';
      node.appendChild(flag);
    }

    if (lesson.status === 'locked') {
      node.disabled = true;
      node.setAttribute('aria-disabled', 'true');
    } else {
      node.addEventListener('click', () => {
        node.scrollIntoView({ behavior: 'smooth', block: 'center' });
        window.setTimeout(() => {
          openLesson(lesson.id);
        }, 140);
      });
    }

    nodeLayer.appendChild(node);
    window.setTimeout(() => node.classList.add('in-view'), idx * 80);
  });

  if (currentLesson) {
    const currentNode = nodeLayer.querySelector(`[data-lesson-id="${currentLesson.id}"]`);
    if (currentNode) {
      currentNode.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }
}

function showReward(title, text) {
  ui.rewardTitle.textContent = title;
  ui.rewardText.textContent = text;
  ui.rewardToast.classList.remove('hidden');
  window.setTimeout(() => {
    ui.rewardToast.classList.add('hidden');
  }, 1800);
}

async function openLesson(lessonId) {
  const payload = await getJSON(`/api/v1/learning/lesson/${encodeURIComponent(lessonId)}`);
  state.currentLesson = payload;
  state.sessionId = null;
  state.quizIndex = 0;
  state.selectedOption = null;
  state.correctCount = 0;

  ui.lessonTitle.textContent = payload.lesson.lesson_goal || lessonId;
  ui.lessonIntro.textContent = `Words in this lesson: ${payload.lesson.target_words.join(', ')}`;

  ui.quizBox.classList.add('hidden');
  ui.lessonSummary.classList.add('hidden');
  ui.finishLesson.classList.add('hidden');
  ui.startLesson.classList.remove('hidden');
  ui.lessonModal.classList.remove('hidden');
}

function renderQuestion() {
  const questions = state.currentLesson.quiz.questions || [];
  const current = questions[state.quizIndex];
  if (!current) {
    ui.quizBox.classList.add('hidden');
    ui.finishLesson.classList.remove('hidden');
    return false;
  }

  ui.quizBox.classList.remove('hidden');
  ui.quizStage.classList.remove('is-preview', 'is-ready');
  ui.videoCountdown.classList.add('hidden');
  ui.nextQuestion.classList.add('hidden');
  ui.submitAnswer.classList.remove('hidden');
  ui.quizFeedback.textContent = '';
  ui.selectedOption = null;

  ui.quizPrompt.textContent = `Q${state.quizIndex + 1}: ${current.prompt}`;
  ui.quizVideo.src = `/${current.asset}`;
  resetVideoState();

  ui.quizOptions.innerHTML = '';
  current.options.forEach((option) => {
    const btn = document.createElement('button');
    btn.textContent = option;
    btn.addEventListener('click', () => {
      state.selectedOption = option;
      ui.quizOptions.querySelectorAll('button').forEach((b) => b.classList.remove('selected'));
      btn.classList.add('selected');
    });
    ui.quizOptions.appendChild(btn);
  });

  ui.submitAnswer.classList.add('hidden');
  setOptionsState('hidden');
  return true;
}

async function submitCurrentAnswer() {
  const questions = state.currentLesson.quiz.questions || [];
  const current = questions[state.quizIndex];
  if (!current || !state.selectedOption) {
    ui.quizFeedback.textContent = 'Select an answer first.';
    return;
  }

  const result = await getJSON('/api/v1/learning/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: state.sessionId,
      question_id: current.question_id,
      selected: state.selectedOption,
    }),
  });

  if (result.correct) {
    state.correctCount += 1;
    ui.quizFeedback.textContent = `Correct. +${result.xp_delta || 0} Expression Score, +${result.coins_delta || 0} coins.`;
  } else {
    ui.quizFeedback.textContent = `Incorrect. Correct answer: ${result.correct_answer}`;
  }

  ui.submitAnswer.classList.add('hidden');
  ui.nextQuestion.classList.remove('hidden');
}

function gotoNextQuestion() {
  state.quizIndex += 1;
  const hasQuestion = renderQuestion();
  if (hasQuestion) {
    runQuestionIntroSequence().catch((error) => {
      console.error(error);
    });
  }
}

async function startLessonSession() {
  if (ui.lessonDialog.requestFullscreen) {
    try {
      await ui.lessonDialog.requestFullscreen();
      ui.lessonModal.classList.add('is-fullscreen');
    } catch (error) {
      console.warn('Fullscreen unavailable:', error);
    }
  }

  const startResp = await getJSON('/api/v1/learning/session/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      lesson_id: state.currentLesson.lesson.lesson_id,
      sublevel: state.currentLesson.lesson.sublevel,
    }),
  });
  state.sessionId = startResp.session_id;

  ui.startLesson.classList.add('hidden');
  const hasQuestion = renderQuestion();
  if (hasQuestion) {
    await runQuestionIntroSequence();
  }
}

async function finishLessonSession() {
  const result = await getJSON('/api/v1/learning/complete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: state.sessionId,
      lesson_id: state.currentLesson.lesson.lesson_id,
    }),
  });

  state.profile = result.state;
  renderProfile();
  await loadPath();

  ui.quizBox.classList.add('hidden');
  renderLessonSummary(result);
  ui.finishLesson.classList.add('hidden');
  ui.startLesson.classList.add('hidden');
  ui.lessonModal.classList.remove('is-fullscreen');
  if (document.fullscreenElement && document.exitFullscreen) {
    try {
      await document.exitFullscreen();
    } catch (error) {
      console.warn('Could not exit fullscreen:', error);
    }
  }

  const stats = result.stats || {};
  showReward(
    'Lesson Complete',
    `Score ${stats.score_percent || 0}% | +${stats.xp_awarded || 0} Expression Score | +${stats.coins_awarded || 0} coins`
  );
}

function buyFreeze(amount, cost) {
  if ((state.profile.xp || 0) < cost) {
    showReward('Not Enough Expression Score', `Need ${cost} Expression Score to buy ${amount} reserve.`);
    return;
  }

  state.profile.xp -= cost;
  state.profile.streak_freezes = (state.profile.streak_freezes || 0) + amount;
  renderProfile();
  showReward('Energy Reserve Added', `Bought ${amount} reserve for ${cost} Expression Score.`);
}

async function claimDailyChest() {
  if (state.claimInFlight) {
    return;
  }

  if (state.profile.reward_claimed_today) {
    setClaimButtonState(true);
    showReward('Already claimed today', 'You can claim your next reward tomorrow.');
    return;
  }

  state.claimInFlight = true;
  ui.claimReward.disabled = true;
  ui.claimReward.textContent = 'Claiming...';
  try {
    const result = await getJSON('/claim_reward', { method: 'POST' });
    if (result.success) {
      state.profile.xp = Number(result.new_score || state.profile.xp || 0);
      state.profile.reward_claimed_today = true;
      renderProfile();
      showReward('Daily Practice Reward', '+25 Expression Score claimed.');
      return;
    }

    if ((result.message || '').toLowerCase().includes('already claimed')) {
      state.profile.reward_claimed_today = true;
      renderProfile();
      showReward('Already claimed today', result.message || 'You already claimed today.');
      return;
    }

    showReward('Claim Failed', result.message || 'Could not claim reward.');
  } finally {
    state.claimInFlight = false;
    syncClaimButtonFromState();
  }
}

async function loadStateAndQuests() {
  const [profile, questsData] = await Promise.all([
    getJSON('/api/v1/learning/state'),
    getJSON('/api/v1/quests/today'),
  ]);
  state.profile = profile;
  renderProfile();
  renderQuests(questsData.quests || []);
}

async function loadPath() {
  const data = await getJSON('/api/v1/learning/path');
  state.path = data.levels || [];
  renderPath();
}

function bindEvents() {
  ui.refreshPath.addEventListener('click', loadPath);
  ui.closeLesson.addEventListener('click', async () => {
    ui.lessonModal.classList.add('hidden');
    ui.lessonModal.classList.remove('is-fullscreen');
    if (document.fullscreenElement && document.exitFullscreen) {
      try {
        await document.exitFullscreen();
      } catch (error) {
        console.warn('Could not exit fullscreen:', error);
      }
    }
  });
  ui.startLesson.addEventListener('click', startLessonSession);
  ui.submitAnswer.addEventListener('click', () => {
    submitCurrentAnswer().catch((error) => {
      console.error(error);
      ui.quizFeedback.textContent = 'Could not save answer. Please retry.';
    });
  });
  ui.nextQuestion.addEventListener('click', gotoNextQuestion);
  ui.finishLesson.addEventListener('click', finishLessonSession);
  ui.claimReward.addEventListener('click', () => {
    claimDailyChest().catch((error) => {
      console.error(error);
      showReward('Claim Failed', 'Could not claim reward.');
    });
  });
  ui.buyFreezeOne.addEventListener('click', () => buyFreeze(1, 120));
  ui.buyFreezeTwo.addEventListener('click', () => buyFreeze(2, 200));
}

async function boot() {
  initLearningThemeSync();
  bindEvents();
  try {
    await loadStateAndQuests();
    await loadPath();
  } catch (error) {
    console.error(error);
    ui.pathContainer.innerHTML = '<p>Could not load learning data. Refresh after server starts.</p>';
  }
}

document.addEventListener('DOMContentLoaded', boot);

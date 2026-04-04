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
  pathContainer: document.getElementById('island-container') || document.getElementById('pathContainer'),
  victorySound: document.getElementById('victorySound'),
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
  lessonCelebration: document.getElementById('lessonCelebration'),
  celebrationTitle: document.getElementById('celebrationTitle'),
  celebrationMessage: document.getElementById('celebrationMessage'),
  celebrationCorrect: document.getElementById('celebrationCorrect'),
  celebrationAccuracy: document.getElementById('celebrationAccuracy'),
  celebrationFocus: document.getElementById('celebrationFocus'),
};

const VIDEO_PLAYBACK_LOOPS = 2;
const COUNTDOWN_SECONDS = 3;
const COMPLETION_SOUND_KEY = 'vyakt_island_completed_seen_v1';
const RENDER_SCROLL_KEY = 'vyakt_island_scrolled_once_v1';

async function getJSON(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function loadSeenCompletions() {
  try {
    const raw = window.localStorage.getItem(COMPLETION_SOUND_KEY);
    if (!raw) return new Set();
    const ids = JSON.parse(raw);
    if (!Array.isArray(ids)) return new Set();
    return new Set(ids);
  } catch (error) {
    console.warn('Could not read completion cache:', error);
    return new Set();
  }
}

function saveSeenCompletions(seenSet) {
  try {
    window.localStorage.setItem(COMPLETION_SOUND_KEY, JSON.stringify(Array.from(seenSet)));
  } catch (error) {
    console.warn('Could not persist completion cache:', error);
  }
}

function getNewlyCompletedIds(lessons) {
  const completedNow = lessons.filter((lesson) => lesson.uiStatus === 'completed').map((lesson) => String(lesson.id));
  const seen = loadSeenCompletions();
  const newlyCompleted = completedNow.filter((id) => !seen.has(id));
  return {
    newlyCompleted: new Set(newlyCompleted),
    completedNow,
    seen,
  };
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

function renderCelebrationState(result = null) {
  if (!state.currentLesson) return;
  const stats = result?.stats || null;
  const total = stats?.total_questions ?? (state.currentLesson.quiz.questions || []).length;
  const correct = stats?.correct_answers ?? state.correctCount ?? 0;
  const accuracy = stats?.score_percent ?? (total ? Math.round((correct / total) * 100) : 0);

  let focusWord = 'Steady';
  if (accuracy >= 90) focusWord = 'Exceptional';
  else if (accuracy >= 75) focusWord = 'Strong';
  else if (accuracy >= 55) focusWord = 'Growing';
  else focusWord = 'Resilient';

  const xpGained = stats?.xp_awarded ?? 0;
  const coinsGained = stats?.coins_awarded ?? 0;
  const gemsGained = stats?.gems_awarded ?? 0;

  ui.celebrationTitle.textContent = `You completed ${state.currentLesson.lesson.lesson_goal || 'this lesson'}.`;
  if (stats) {
    ui.celebrationMessage.textContent =
      `Beautiful progress: +${xpGained} Expression Score, +${coinsGained} coins, +${gemsGained} gems.`;
  } else {
    ui.celebrationMessage.textContent = 'Every sign you practiced today made your voice clearer.';
  }
  ui.celebrationCorrect.textContent = `${correct}/${total}`;
  ui.celebrationAccuracy.textContent = `${accuracy}%`;
  ui.celebrationFocus.textContent = focusWord;
  ui.lessonCelebration.classList.remove('hidden');
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
  if (status === 'unlocked') return 'current';
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
  const lessons = flattenLessonTrackData().map((lesson) => ({
    ...lesson,
    title: lesson.label,
    description: usageFromLesson({ goal: lesson.goal }, lesson.section),
    uiStatus: lessonButtonClass(lesson.status),
  }));

  if (!lessons.length) {
    ui.pathContainer.innerHTML = '<p>Path data unavailable.</p>';
    return;
  }
  const completionState = getNewlyCompletedIds(lessons);

  const journey = document.createElement('div');
  journey.className = 'island-journey-track';

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.classList.add('island-path-svg');
  svg.innerHTML = `
    <path class="island-path-base"></path>
    <path class="island-path-progress"></path>
  `;

  const rows = document.createElement('div');
  rows.className = 'island-rows';

  journey.appendChild(svg);
  journey.appendChild(rows);
  ui.pathContainer.appendChild(journey);

  const currentLesson = lessons.find((item) => item.uiStatus === 'current');

  lessons.forEach((lesson, index) => {
    const row = document.createElement('div');
    row.className = `island-row ${lesson.uiStatus}`;
    if (completionState.newlyCompleted.has(String(lesson.id))) {
      row.classList.add('newly-completed');
    }
    row.setAttribute('data-lesson-id', lesson.id);

    const visual = document.createElement('div');
    visual.className = 'island-visual';

    const islandImg = document.createElement('img');
    islandImg.src = '/static/images/island.png';
    islandImg.className = 'island-img';
    islandImg.alt = `${lesson.title} island`;

    const flagImg = document.createElement('img');
    flagImg.src = '/static/images/flag.png';
    flagImg.className = 'flag';
    flagImg.alt = 'Conquered flag';

    const lockBadge = document.createElement('span');
    lockBadge.className = 'lock-badge';
    lockBadge.textContent = '🔒';

    visual.appendChild(islandImg);
    visual.appendChild(flagImg);
    if (lesson.uiStatus === 'locked') {
      visual.appendChild(lockBadge);
    }

    const content = document.createElement('div');
    content.className = 'island-content';

    const title = document.createElement('h3');
    title.textContent = lesson.title;

    const desc = document.createElement('p');
    desc.textContent = lesson.description;

    content.appendChild(title);
    content.appendChild(desc);
    row.appendChild(visual);
    row.appendChild(content);

    if (lesson.uiStatus === 'locked') {
      row.setAttribute('aria-disabled', 'true');
    } else if (lesson.uiStatus === 'current') {
      row.addEventListener('click', () => {
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
        window.setTimeout(() => openLesson(lesson.id), 120);
      });
    } else {
      row.addEventListener('click', () => {
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    }

    rows.appendChild(row);
    window.setTimeout(() => row.classList.add('in-view'), index * 90);
  });

  const drawConnectorPath = () => {
    const basePath = svg.querySelector('.island-path-base');
    const progressPath = svg.querySelector('.island-path-progress');
    const rowEls = Array.from(rows.querySelectorAll('.island-row'));
    if (rowEls.length < 2 || !basePath || !progressPath) return;

    const svgRect = journey.getBoundingClientRect();
    const points = rowEls.map((row) => {
      const visual = row.querySelector('.island-visual');
      const rect = visual.getBoundingClientRect();
      return {
        x: (rect.left + (rect.width / 2)) - svgRect.left,
        y: (rect.top + (rect.height / 2)) - svgRect.top,
      };
    });

    const d = points.reduce((acc, point, idx) => {
      if (idx === 0) return `M ${point.x} ${point.y}`;
      const prev = points[idx - 1];
      const dx = point.x - prev.x;
      const dy = point.y - prev.y;
      const turnDir = dx >= 0 ? 1 : -1;
      const verticalDir = dy >= 0 ? 1 : -1;
      const corner = Math.max(14, Math.min(32, Math.min(Math.abs(dx), Math.abs(dy)) * 0.22));
      const midY = prev.y + (dy * 0.55);
      const y1 = midY - (verticalDir * corner);
      const x1 = prev.x + (turnDir * corner);
      const x2 = point.x - (turnDir * corner);
      const y2 = midY + (verticalDir * corner);

      return `${acc}
        L ${prev.x} ${y1}
        Q ${prev.x} ${midY}, ${x1} ${midY}
        L ${x2} ${midY}
        Q ${point.x} ${midY}, ${point.x} ${y2}
        L ${point.x} ${point.y}`;
    }, '');

    basePath.setAttribute('d', d);
    progressPath.setAttribute('d', d);
    const totalLength = progressPath.getTotalLength();
    const completedFromStart = lessons.findIndex((lesson) => lesson.uiStatus !== 'completed');
    const completedCount = completedFromStart === -1 ? lessons.length : completedFromStart;
    const totalSegments = Math.max(1, lessons.length - 1);
    const progressRatio = Math.max(0, Math.min(1, completedCount / totalSegments));
    const progressLength = totalLength * progressRatio;

    basePath.style.strokeDasharray = `${totalLength}`;
    basePath.style.strokeDashoffset = '0';
    progressPath.style.strokeDasharray = `${totalLength}`;
    progressPath.style.strokeDashoffset = `${Math.max(0, totalLength - progressLength)}`;
    progressPath.classList.add('draw');
  };

  requestAnimationFrame(drawConnectorPath);
  const onResize = () => drawConnectorPath();
  window.addEventListener('resize', onResize, { passive: true });
  window.setTimeout(() => window.removeEventListener('resize', onResize), 120000);

  if (completionState.newlyCompleted.size > 0) {
    if (ui.victorySound) {
      const playResult = ui.victorySound.play();
      if (playResult && typeof playResult.catch === 'function') {
        playResult.catch(() => {});
      }
    }
    completionState.completedNow.forEach((id) => completionState.seen.add(id));
    saveSeenCompletions(completionState.seen);
  }

  if (currentLesson && !window.sessionStorage.getItem(RENDER_SCROLL_KEY)) {
    const currentRow = rows.querySelector(`[data-lesson-id="${currentLesson.id}"]`);
    if (currentRow) {
      currentRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      window.sessionStorage.setItem(RENDER_SCROLL_KEY, '1');
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
  ui.lessonIntro.classList.remove('hidden');

  ui.quizBox.classList.add('hidden');
  ui.lessonSummary.classList.add('hidden');
  ui.lessonCelebration.classList.add('hidden');
  ui.finishLesson.classList.add('hidden');
  ui.startLesson.classList.remove('hidden');
  ui.finishLesson.textContent = 'Finish Lesson';
  ui.lessonModal.classList.remove('hidden');
}

function renderQuestion() {
  const questions = state.currentLesson.quiz.questions || [];
  const current = questions[state.quizIndex];
  if (!current) {
    ui.quizBox.classList.add('hidden');
    renderCelebrationState();
    ui.finishLesson.classList.remove('hidden');
    return false;
  }

  ui.quizBox.classList.remove('hidden');
  ui.lessonIntro.classList.add('hidden');
  ui.lessonCelebration.classList.add('hidden');
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
  ui.lessonIntro.classList.add('hidden');
  const hasQuestion = renderQuestion();
  if (hasQuestion) {
    await runQuestionIntroSequence();
  }
}

async function finishLessonSession() {
  ui.finishLesson.disabled = true;
  ui.finishLesson.textContent = 'Generating Report...';
  try {
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
    renderCelebrationState(result);
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
  } finally {
    ui.finishLesson.disabled = false;
    ui.finishLesson.textContent = 'Finish Lesson';
  }
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

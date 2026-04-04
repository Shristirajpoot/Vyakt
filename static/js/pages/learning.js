const state = {
  profile: { xp: 0, hearts: 5, streak_days: 0, badges: [], completed_lessons: [], streak_freezes: 0 },
  path: [],
  currentLesson: null,
  sessionId: null,
  quizIndex: 0,
  selectedOption: null,
  correctCount: 0,
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
    li.textContent = 'Complete lessons to unlock badges.';
    ui.badgeList.appendChild(li);
    return;
  }
  recent.forEach((badge) => {
    const li = document.createElement('li');
    li.textContent = badge;
    ui.badgeList.appendChild(li);
  });

  renderLeagueCard();
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
    `Correct ${correct}/${total} | Score ${score}% | Points ${points} | XP +${xp} | Coins +${coins} | Gems +${gems}`;

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
    ui.leagueHint.textContent = `Earn ${need} XP to reach ${nextTier.name}.`;
  } else {
    ui.leagueHint.textContent = 'You are in the top league. Keep the momentum.';
  }
}

function renderQuests(quests) {
  ui.questList.innerHTML = '';
  quests.forEach((quest) => {
    const li = document.createElement('li');
    li.textContent = `${quest.title} (+${quest.reward_xp} XP)`;
    ui.questList.appendChild(li);
  });
}

function lessonButtonClass(lesson) {
  if (lesson.completed) return 'lesson-pill completed';
  if (lesson.unlocked) return 'lesson-pill unlocked';
  return 'lesson-pill locked';
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
  await sleep(260);
  ui.lessonDialog.classList.remove('is-blurred');
  setOptionsState('visible');
  ui.submitAnswer.classList.remove('hidden');
}

function renderPath() {
  ui.pathContainer.innerHTML = '';

  state.path.forEach((level) => {
    const levelCard = document.createElement('section');
    levelCard.className = 'level-card';

    const title = document.createElement('h3');
    title.className = 'level-title';
    title.textContent = level.name;
    levelCard.appendChild(title);

    level.sublevels.forEach((sub) => {
      const row = document.createElement('div');
      row.className = 'sublevel-row';

      const subTitle = document.createElement('h4');
      subTitle.textContent = sub.name;
      row.appendChild(subTitle);

      const grid = document.createElement('div');
      grid.className = 'lessons-grid';

      sub.lessons.forEach((lesson) => {
        const button = document.createElement('button');
        button.className = lessonButtonClass(lesson);
        button.textContent = lesson.label;
        button.title = lesson.goal;

        if (!lesson.unlocked && !lesson.completed) {
          button.disabled = true;
        } else {
          button.addEventListener('click', () => openLesson(lesson.lesson_id));
        }

        grid.appendChild(button);
      });

      row.appendChild(grid);
      levelCard.appendChild(row);
    });

    ui.pathContainer.appendChild(levelCard);
  });
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
    ui.quizFeedback.textContent = `Correct. +${result.xp_delta || 0} XP, +${result.coins_delta || 0} coins.`;
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
    `Score ${stats.score_percent || 0}% | +${stats.xp_awarded || 0} XP | +${stats.coins_awarded || 0} coins`
  );
}

function buyFreeze(amount, cost) {
  if ((state.profile.xp || 0) < cost) {
    showReward('Not Enough XP', `Need ${cost} XP to buy ${amount} freeze.`);
    return;
  }

  state.profile.xp -= cost;
  state.profile.streak_freezes = (state.profile.streak_freezes || 0) + amount;
  renderProfile();
  showReward('Shop Purchase', `Bought ${amount} freeze for ${cost} XP.`);
}

function claimDailyChest() {
  const reward = 25;
  state.profile.xp = (state.profile.xp || 0) + reward;
  renderProfile();
  showReward('Daily Chest', `+${reward} XP bonus claimed.`);
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
  ui.claimReward.addEventListener('click', claimDailyChest);
  ui.buyFreezeOne.addEventListener('click', () => buyFreeze(1, 120));
  ui.buyFreezeTwo.addEventListener('click', () => buyFreeze(2, 200));
}

async function boot() {
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

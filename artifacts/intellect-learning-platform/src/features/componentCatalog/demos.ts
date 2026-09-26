import type { Block } from '@/lib/api';

export type ComponentDemo = {
  block: Block;
  usage: string;
  interaction: string;
};

export const componentDemos: Record<string, ComponentDemo> = {
  'short-explanation': {
    usage: 'В начале новой темы, чтобы коротко объяснить правило и выделить главные идеи.',
    interaction: 'Информационный блок: формулы, ключевые понятия и важная подсказка.',
    block: {
      component: 'ShortExplanation',
      content: {
        title: 'Линейное уравнение',
        text: 'Линейное уравнение имеет вид $ax + b = 0$, где $a \\neq 0$. Чтобы найти $x$, перенесите свободный член и разделите обе части на коэффициент при неизвестной.',
        key_concepts: ['Равносильные преобразования', 'Коэффициент', 'Корень уравнения'],
        callout: 'Любое действие нужно выполнять с обеими частями уравнения.',
      },
    },
  },
  'key-concept': {
    usage: 'После объяснения, чтобы зафиксировать один термин через определение, пример и контрпример.',
    interaction: 'Сравните пример с контрпримером и обсудите различие с классом.',
    block: {
      component: 'KeyConcept',
      content: {
        term: 'Метафора',
        definition: 'Скрытое сравнение, при котором свойства одного предмета переносятся на другой.',
        example: '«Золотая осень укрыла город» — осени приписано действие живого существа.',
        non_example: '«Листья жёлтые, как золото» — это прямое сравнение со словом «как».',
        visual_hint: 'Ищите переносное значение без слов «как», «будто» и «словно».',
      },
    },
  },
  'worked-example': {
    usage: 'Перед самостоятельной работой, чтобы показать образец рассуждения по шагам.',
    interaction: 'Нажимайте «Следующий шаг», раскрывайте подсказки и сравните итоговый ответ.',
    block: {
      component: 'WorkedExample',
      content: {
        problem: 'Решите уравнение: $3x - 7 = 11$.',
        steps: [
          { description: 'Прибавим 7 к обеим частям.', math: '3x = 18', hint: 'Избавляемся от свободного члена.' },
          { description: 'Разделим обе части на 3.', math: 'x = 6', hint: 'Коэффициент при $x$ должен стать равен 1.' },
          { description: 'Проверим подстановкой.', math: '3 \\cdot 6 - 7 = 11' },
        ],
        final_answer: '$x = 6$',
      },
    },
  },
  'guided-practice': {
    usage: 'Сразу после разбора примера, когда ученику ещё нужна поддержка.',
    interaction: 'Введите ответ 4. Если сложно — открывайте подсказки по одной.',
    block: {
      component: 'GuidedPractice',
      content: {
        question: 'Решите уравнение: $2x + 5 = 13$.',
        hints: ['Вычтите 5 из обеих частей.', 'Получится $2x = 8$.', 'Разделите обе части на 2.'],
        input_type: 'numeric',
        correct_answer: '4',
        explanation: '$2x + 5 = 13 \\Rightarrow 2x = 8 \\Rightarrow x = 4$.',
      },
    },
  },
  'independent-problem': {
    usage: 'Для самостоятельной проверки применения изученного правила.',
    interaction: 'Выберите один вариант и нажмите «Ответить». Доступно до трёх попыток.',
    block: {
      component: 'IndependentProblem',
      content: {
        question: 'Какое значение $x$ является корнем уравнения $5x - 10 = 15$?',
        type: 'multiple_choice',
        options: ['$x = 1$', '$x = 3$', '$x = 5$', '$x = 7$'],
        correct_answer: '$x = 5$',
        explanation: '$5x = 25$, поэтому $x = 5$.',
        difficulty: 'basic',
      },
    },
  },
  'retrieval-check': {
    usage: 'Для быстрой проверки, помнит ли ученик ключевой факт без подсказок.',
    interaction: 'Нажмите на вариант ответа — обратная связь появится сразу.',
    block: {
      component: 'RetrievalCheck',
      content: {
        question: 'Кто написал роман «Капитанская дочка»?',
        options: ['М. Ю. Лермонтов', 'А. С. Пушкин', 'Н. В. Гоголь', 'И. С. Тургенев'],
        correct_answer: 'А. С. Пушкин',
        explanation: 'Александр Сергеевич Пушкин создал роман в 1830-х годах.',
      },
    },
  },
  'mind-map': {
    usage: 'Для обзора темы и визуального показа связей между понятиями.',
    interaction: 'Изучите ветви карты от центрального понятия к связанным элементам.',
    block: {
      component: 'MindMap',
      content: {
        title: 'Система образов романа',
        central_concept: 'Капитанская дочка',
        branches: [
          { label: 'Гринёв', children: ['Честь', 'Взросление'] },
          { label: 'Маша', children: ['Верность', 'Смелость'] },
          { label: 'Пугачёв', children: ['Милосердие', 'Бунт'] },
        ],
      },
    },
  },
  timeline: {
    usage: 'Для историко-литературного контекста или последовательности событий произведения.',
    interaction: 'Прокручивайте шкалу по горизонтали и изучайте события по порядку.',
    block: {
      component: 'Timeline',
      content: {
        title: 'Жизнь и творчество А. С. Пушкина',
        events: [
          { date: '1799', label: 'Рождение поэта', description: 'Москва, Немецкая слобода.' },
          { date: '1811', label: 'Поступление в лицей', description: 'Начало обучения в Царском Селе.' },
          { date: '1820', label: '«Руслан и Людмила»', description: 'Выход первой крупной поэмы.' },
          { date: '1836', label: '«Капитанская дочка»', description: 'Публикация исторического романа.' },
        ],
      },
    },
  },
  'text-evidence-picker': {
    usage: 'Чтобы научить подтверждать вывод точной цитатой из текста.',
    interaction: 'Выберите предложение, которое подтверждает тезис, затем проверьте ответ.',
    block: {
      component: 'TextEvidencePicker',
      content: {
        passage: 'Маша отказалась от брака без благословения родителей Гринёва. Она была готова отказаться от личного счастья ради их спокойствия. Позже героиня отправилась к императрице, чтобы спасти Петра.',
        claim: 'Маша ставит нравственный долг выше личной выгоды.',
        correct_segments: ['Она была готова отказаться от личного счастья ради их спокойствия.'],
        explanation: 'Выбранное предложение прямо показывает готовность героини пожертвовать собственным счастьем.',
      },
    },
  },
  'argument-builder': {
    usage: 'При подготовке к развёрнутому ответу или сочинению по литературе.',
    interaction: 'Выберите тезис и два подходящих доказательства, затем соберите аргумент.',
    block: {
      component: 'ArgumentBuilder',
      content: {
        prompt: 'Докажите, что Гринёв сохраняет понятие чести в трудных обстоятельствах.',
        thesis_options: [
          'Гринёв взрослеет, потому что остаётся верен нравственным принципам.',
          'Гринёв меняется только благодаря случайным событиям.',
          'Главная черта Гринёва — стремление к богатству.',
        ],
        evidence_pool: [
          'Он отказывается присягать Пугачёву даже под угрозой смерти.',
          'Он возвращает долг Зурину после проигрыша.',
          'Он приезжает в Белогорскую крепость зимой.',
          'Савельич сопровождает его в поездке.',
        ],
        correct_thesis: 'Гринёв взрослеет, потому что остаётся верен нравственным принципам.',
        correct_evidence: [
          'Он отказывается присягать Пугачёву даже под угрозой смерти.',
          'Он возвращает долг Зурину после проигрыша.',
        ],
        model_reasoning: 'Оба эпизода показывают, что герой выполняет моральные обязательства, даже когда это опасно или невыгодно.',
      },
    },
  },
  'interactive-graph': {
    usage: 'Чтобы связать формулу с её графическим представлением и исследовать зависимость.',
    interaction: 'Изменяйте параметр ползунком и наблюдайте за графиком функции.',
    block: {
      component: 'InteractiveGraph',
      content: {
        title: 'График линейной функции',
        description: 'Исследуйте, как коэффициент $k$ влияет на функцию $y = kx$.',
        graph_type: 'line',
        data_points: [
          { x: -2, y: -4 }, { x: -1, y: -2 }, { x: 0, y: 0 }, { x: 1, y: 2 }, { x: 2, y: 4 },
        ],
        x_label: 'x',
        y_label: 'y',
        interactive_params: [
          { name: 'k', label: 'Коэффициент k', min: -3, max: 3, step: 0.5, default: 2, formula_description: 'y = kx' },
        ],
      },
    },
  },
  presentation: {
    usage: 'Для структурированной подачи материала небольшими последовательными слайдами.',
    interaction: 'Листайте слайды стрелками или нажимайте на точки навигации.',
    block: {
      component: 'Presentation',
      content: {
        title: 'Три шага анализа героя',
        slides: [
          {
            heading: '1. Поступки',
            body: 'Найдите решения героя в ключевых ситуациях и определите их мотивы.',
            visual: '<svg viewBox="0 0 240 160" xmlns="http://www.w3.org/2000/svg"><rect x="24" y="22" width="192" height="116" rx="18" fill="#eef2ff"/><path d="M64 82h112M64 58h72M64 106h88" stroke="#4f46e5" stroke-width="8" stroke-linecap="round"/></svg>',
          },
          { heading: '2. Речь', body: 'Обратите внимание на слова героя, интонацию и изменения его речи.' },
          { heading: '3. Авторская позиция', body: 'Сопоставьте поступки героя с оценкой автора и других персонажей.' },
        ],
      },
    },
  },
  illustration: {
    usage: 'Когда схему, процесс или устройство проще понять визуально.',
    interaction: 'Изучите подписи и связь элементов на иллюстрации.',
    block: {
      component: 'Illustration',
      content: {
        title: 'Баланс уравнения',
        description: 'Равенство можно представить как весы: обе стороны должны оставаться равными.',
        svg_content: '<svg viewBox="0 0 520 220" xmlns="http://www.w3.org/2000/svg"><rect width="520" height="220" rx="24" fill="#f8fafc"/><path d="M260 42v126M145 80h230M145 80l-54 82M145 80l54 82M375 80l-54 82M375 80l54 82" stroke="#4f46e5" stroke-width="8" stroke-linecap="round"/><path d="M68 162h154c-7 25-31 38-77 38s-70-13-77-38zm230 0h154c-7 25-31 38-77 38s-70-13-77-38z" fill="#c7d2fe"/><text x="145" y="187" text-anchor="middle" font-size="22" font-family="sans-serif" fill="#312e81">2x + 5</text><text x="375" y="187" text-anchor="middle" font-size="22" font-family="sans-serif" fill="#312e81">13</text></svg>',
        caption: 'Если вычесть 5 слева, нужно вычесть 5 и справа.',
      },
    },
  },
  'mastery-check': {
    usage: 'В конце урока для итоговой проверки нескольких аспектов темы.',
    interaction: 'Ответьте на три вопроса по очереди и получите итоговый уровень освоения.',
    block: {
      component: 'MasteryCheck',
      content: {
        questions: [
          {
            question: 'Чему равен корень уравнения $x + 7 = 12$?',
            type: 'multiple_choice',
            options: ['3', '5', '7', '19'],
            correct_answer: '5',
            explanation: '$x = 12 - 7 = 5$.',
            dimension: 'Понимание',
          },
          {
            question: 'Решите: $3x = 21$.',
            type: 'numeric',
            correct_answer: '7',
            explanation: '$x = 21 : 3 = 7$.',
            dimension: 'Применение',
          },
          {
            question: 'Какое преобразование равносильно для $2x - 4 = 10$?',
            type: 'multiple_choice',
            options: ['$2x = 6$', '$2x = 14$', '$x = 14$', '$2x = -14$'],
            correct_answer: '$2x = 14$',
            explanation: 'К обеим частям нужно прибавить 4.',
            dimension: 'Рассуждение',
          },
        ],
      },
    },
  },
  reflection: {
    usage: 'В завершение урока, чтобы ученик оценил понимание и сформулировал затруднения.',
    interaction: 'Выберите уровень уверенности, напишите короткий ответ и отправьте рефлексию.',
    block: {
      component: 'Reflection',
      content: {
        prompt: 'Что сегодня помогло вам лучше понять способ решения уравнений?',
        scale_question: 'Насколько уверенно вы теперь решаете линейные уравнения?',
        scale_labels: ['Пока сложно', 'Нужна практика', 'Почти уверен', 'Могу объяснить другому'],
      },
    },
  },
  'sort-and-classify': {
    usage: 'Когда нужно понять группу признаков: части речи, типы реакций, виды источников.',
    interaction: 'Перетащите элементы в правильные группы и проверьте классификацию.',
    block: {
      component: 'SortAndClassify',
      content: {
        title: 'Классификация природных объектов',
        instruction: 'Распределите объекты по оболочкам Земли.',
        groups: [
          { id: 'hydro', label: 'Гидросфера' },
          { id: 'litho', label: 'Литосфера' },
        ],
        items: [
          { id: 'river', label: 'Река', correct_group: 'hydro' },
          { id: 'lake', label: 'Озеро', correct_group: 'hydro' },
          { id: 'mountain', label: 'Гора', correct_group: 'litho' },
          { id: 'plate', label: 'Плита', correct_group: 'litho' },
        ],
        explanation: 'Вода относится к гидросфере, твёрдая оболочка и формы рельефа — к литосфере.',
      },
    },
  },
  'process-builder': {
    usage: 'Для причинных цепочек, циклов, алгоритмов и последовательностей процессов.',
    interaction: 'Соедините узлы стрелками в правильном порядке.',
    block: {
      component: 'ProcessBuilder',
      content: {
        title: 'Круговорот воды',
        instruction: 'Соедините этапы круговорота воды.',
        steps: [
          { id: 'evaporation', label: 'Испарение' },
          { id: 'condensation', label: 'Конденсация' },
          { id: 'precipitation', label: 'Осадки' },
          { id: 'runoff', label: 'Сток' },
        ],
        correct_edges: [
          { from: 'evaporation', to: 'condensation' },
          { from: 'condensation', to: 'precipitation' },
          { from: 'precipitation', to: 'runoff' },
        ],
        explanation: 'Вода испаряется, превращается в облака, выпадает осадками и возвращается стоком.',
      },
    },
  },
  'argument-map': {
    usage: 'Для истории, литературы и общества, когда важно связать тезис и доказательства.',
    interaction: 'Соедините доказательства с тезисом и объяснением.',
    block: {
      component: 'ArgumentMap',
      content: {
        title: 'Карта аргумента',
        prompt: 'Докажите, что герой действует ответственно.',
        nodes: [
          { id: 'claim', kind: 'claim', label: 'Герой действует ответственно' },
          { id: 'e1', kind: 'evidence', label: 'Он предупреждает других об опасности' },
          { id: 'e2', kind: 'evidence', label: 'Он исправляет свою ошибку' },
          { id: 'reason', kind: 'reasoning', label: 'Оба поступка показывают заботу о последствиях' },
        ],
        correct_links: [
          { from: 'e1', to: 'claim' },
          { from: 'e2', to: 'claim' },
          { from: 'reason', to: 'claim' },
        ],
        explanation: 'Аргумент сильный, когда каждое доказательство прямо поддерживает тезис.',
      },
    },
  },
  'branching-scenario': {
    usage: 'Для лабораторий, гражданских решений, коммуникации и техники безопасности.',
    interaction: 'Выбирайте действия и наблюдайте последствия сценария.',
    block: {
      component: 'BranchingScenario',
      content: {
        title: 'Безопасный опыт',
        context: 'Вы заметили неизвестный раствор на лабораторном столе.',
        start_node_id: 'start',
        nodes: [
          { id: 'start', title: 'Первое действие', text: 'Что нужно сделать?', choices: [
            { label: 'Понюхать раствор', next: 'bad', feedback: 'Это опасно: пары могут быть вредными.' },
            { label: 'Сообщить учителю и проверить маркировку', next: 'good', feedback: 'Правильно: сначала безопасность и идентификация.' },
          ] },
          { id: 'good', title: 'Безопасный выбор', text: 'Опыт можно продолжать только после инструктажа.', terminal: true, success: true },
          { id: 'bad', title: 'Опасный выбор', text: 'Нарушена техника безопасности.', terminal: true, success: false },
        ],
        success_feedback: 'Вы выбрали безопасную стратегию.',
        failure_feedback: 'В лаборатории нельзя проверять неизвестные вещества органами чувств.',
      },
    },
  },
  'misconception-debugger': {
    usage: 'Для работы с типичными ошибками в решении, коде, грамматике или опыте.',
    interaction: 'Выберите ошибочный шаг и соберите правильное исправление.',
    block: {
      component: 'MisconceptionDebugger',
      content: {
        title: 'Найдите ошибку',
        prompt: 'Ученик решает: 2x + 5 = 13.',
        steps: [
          { id: 's1', text: '2x + 5 = 13' },
          { id: 's2', text: '2x = 13 + 5', is_error: true },
          { id: 's3', text: '2x = 18' },
          { id: 's4', text: 'x = 9' },
        ],
        repair_steps: ['Вычесть 5 из обеих частей', 'Получить 2x = 8', 'Разделить обе части на 2', 'Получить x = 4'],
        explanation: 'При переносе +5 нужно вычитать 5, а не прибавлять.',
      },
    },
  },
  'prediction-lab': {
    usage: 'Для объяснения через прогноз, наблюдение и вывод.',
    interaction: 'Сначала сделайте прогноз, затем сравните его с наблюдением.',
    block: {
      component: 'PredictionLab',
      content: {
        title: 'Что будет с температурой?',
        question: 'Если увеличить высоту над уровнем моря, температура воздуха обычно...',
        options: [
          { id: 'rise', label: 'повышается' },
          { id: 'fall', label: 'понижается' },
          { id: 'same', label: 'не меняется' },
        ],
        correct_prediction: 'fall',
        observation_title: 'Наблюдение',
        observations: [
          { label: '0 м', value: '+24°C' },
          { label: '1000 м', value: '+18°C' },
          { label: '2000 м', value: '+12°C' },
        ],
        explanation: 'С высотой воздух обычно охлаждается, поэтому температура уменьшается.',
      },
    },
  },
  'data-investigation': {
    usage: 'Для анализа графиков, таблиц и закономерностей.',
    interaction: 'Изучите диаграмму и выберите верный вывод.',
    block: {
      component: 'DataInvestigation',
      content: {
        title: 'Рост растения',
        description: 'Сравните рост растения по дням наблюдения.',
        vega_lite_spec: {
          $schema: 'https://vega.github.io/schema/vega-lite/v5.json',
          data: { values: [{ day: 1, height: 2 }, { day: 2, height: 4 }, { day: 3, height: 7 }, { day: 4, height: 11 }] },
          mark: 'line',
          encoding: { x: { field: 'day', type: 'ordinal' }, y: { field: 'height', type: 'quantitative' } },
        },
        question: {
          question: 'Какой вывод лучше всего описывает данные?',
          options: ['Рост замедляется', 'Рост ускоряется', 'Высота не меняется', 'Данных недостаточно'],
          correct_answer: 'Рост ускоряется',
        },
        explanation: 'Разница между днями увеличивается: +2, +3, +4.',
      },
    },
  },
  'physics-sandbox': {
    usage: 'Для объяснения физической зависимости через управляемую модель.',
    interaction: 'Измените параметры, перезапустите модель и ответьте на вопрос.',
    block: {
      component: 'PhysicsSandbox',
      content: {
        title: 'Падение тела',
        prompt: 'Понаблюдайте, как гравитация влияет на движение шарика.',
        bodies: [
          { shape: 'circle', x: 120, y: 60, radius: 24 },
          { shape: 'rectangle', x: 360, y: 330, width: 660, height: 28, is_static: true },
        ],
        params: [
          { name: 'gravity', label: 'Гравитация', min: 0.2, max: 2, step: 0.1, default: 1 },
          { name: 'restitution', label: 'Упругость', min: 0, max: 1, step: 0.1, default: 0.5 },
        ],
        question: 'Что произойдёт при увеличении гравитации?',
        options: ['Шарик падает быстрее', 'Шарик исчезает', 'Шарик становится легче', 'Движение не меняется'],
        correct_answer: 'Шарик падает быстрее',
        explanation: 'Большая гравитация увеличивает ускорение падения.',
      },
    },
  },
  'hotspot-investigation': {
    usage: 'Для исследования схемы, карты, прибора, клетки или изображения.',
    interaction: 'Нажмите нужные зоны и проверьте выбор.',
    block: {
      component: 'HotspotInvestigation',
      content: {
        title: 'Части клетки',
        instruction: 'Выберите структуры, которые участвуют в управлении клеткой и выработке энергии.',
        svg_content: '<svg viewBox="0 0 500 260" xmlns="http://www.w3.org/2000/svg"><rect width="500" height="260" rx="24" fill="#f8fafc"/><ellipse cx="250" cy="130" rx="190" ry="85" fill="#dcfce7" stroke="#16a34a" stroke-width="4"/><circle cx="220" cy="125" r="42" fill="#bfdbfe" stroke="#2563eb" stroke-width="4"/><ellipse cx="330" cy="145" rx="42" ry="18" fill="#fed7aa" stroke="#ea580c" stroke-width="4"/><ellipse cx="145" cy="105" rx="35" ry="16" fill="#ddd6fe" stroke="#7c3aed" stroke-width="4"/></svg>',
        hotspots: [
          { id: 'nucleus', label: 'Ядро', x: 44, y: 48, feedback: 'Ядро хранит наследственную информацию.', is_correct: true },
          { id: 'mitochondria', label: 'Митохондрия', x: 66, y: 56, feedback: 'Митохондрии связаны с энергией клетки.', is_correct: true },
          { id: 'vacuole', label: 'Вакуоль', x: 29, y: 40, feedback: 'Вакуоль хранит вещества.' },
        ],
        required_hotspots: ['nucleus', 'mitochondria'],
        explanation: 'Ядро управляет клеткой, митохондрии участвуют в получении энергии.',
      },
    },
  },
  'code-blocks-lab': {
    usage: 'Для информатики и алгоритмического мышления.',
    interaction: 'Соберите алгоритм из Blockly-блоков и проверьте нужные конструкции.',
    block: {
      component: 'CodeBlocksLab',
      content: {
        title: 'Алгоритм с повторением',
        task: 'Соберите алгоритм, который использует цикл и вывод значения.',
        toolbox_xml: '<xml><block type="controls_repeat_ext"></block><block type="math_number"></block><block type="text_print"></block><block type="text"></block></xml>',
        expected_block_types: ['controls_repeat_ext', 'text_print'],
        explanation: 'В алгоритме есть повторение и действие вывода.',
      },
    },
  },
  'function-explorer': {
    usage: 'Для функций в алгебре: как параметры формулы меняют график (y = kx + b, y = ax², y = k/x).',
    interaction: 'Сначала предскажите, что станет с графиком, затем двигайте ползунки и совместите график с пунктиром.',
    block: {
      component: 'FunctionExplorer',
      content: {
        title: 'Как k и b управляют прямой',
        instruction: 'Подберите k и b так, чтобы прямая прошла через отмеченные точки.',
        formula: 'k*x + b',
        params: [
          { name: 'k', label: 'Угловой коэффициент $k$', min: -3, max: 3, step: 0.5, default: 1 },
          { name: 'b', label: 'Свободный член $b$', min: -4, max: 4, step: 1, default: 0 },
        ],
        x_range: [-5, 5],
        y_range: [-5, 5],
        target: { params: { k: 2, b: -1 } },
        points: [{ x: 0, y: -1, label: 'A(0; −1)' }, { x: 2, y: 3, label: 'B(2; 3)' }],
        prediction: {
          question: 'что станет с прямой, если $b$ увеличить на 2?',
          options: ['Сдвинется вверх на 2', 'Станет круче', 'Сдвинется вправо на 2', 'Повернётся вокруг начала координат'],
          correct_answer: 'Сдвинется вверх на 2',
          explanation: '$b$ — точка пересечения с осью $y$: каждая точка прямой поднимается на столько же.',
        },
        explanation: 'Прямая проходит через $A(0; -1)$, значит $b = -1$. От $A$ к $B$ $y$ вырос на 4, а $x$ — на 2: $k = 4 : 2 = 2$.',
      },
    },
  },
  'step-solver': {
    usage: 'Для математики: ученик сам пишет решение строка за строкой, как в тетради.',
    interaction: 'Введите следующую строку: каждое преобразование проверяется сразу, типичная ошибка названа.',
    block: {
      component: 'StepSolver',
      content: {
        title: 'Решаю уравнение по шагам',
        instruction: 'Решите уравнение, записывая каждое преобразование отдельной строкой.',
        kind: 'equation',
        start: 'x^2 = 3x',
        steps: [
          { hint: 'Перенесите всё в левую часть: справа должен остаться 0.', expected: 'x^2 - 3x = 0' },
          { hint: 'Вынесите общий множитель x за скобки.', expected: 'x(x - 3) = 0' },
          { hint: 'Произведение равно нулю, когда хотя бы один множитель равен нулю.', expected: 'x = 0 или x = 3' },
        ],
        final_answer: ['x = 0 или x = 3'],
        mistakes: [{ wrong: 'x = 3', message: 'Делить обе части на $x$ нельзя: так потерян корень $x = 0$.' }],
        explanation: 'Переносим всё в одну часть, раскладываем на множители и приравниваем каждый множитель к нулю — корней два.',
      },
    },
  },
  'cause-effect-map': {
    usage: 'Для истории и обществознания: отличить причину от повода, увидеть последствия события.',
    interaction: 'Выберите роль каждого фактора — схема сама достроит стрелки к событию и от него.',
    block: {
      component: 'CauseEffectMap',
      content: {
        title: 'Почему восстали кыргызы?',
        instruction: 'Определите роль каждого фактора.',
        event: { label: 'Восстание против Кокандского ханства', year: 1845 },
        factors: [
          { id: 'tax', label: 'Тяжёлые налоги и повинности', role: 'cause', kind: 'economic', explanation: 'Налоги копились годами и разоряли кочевников.' },
          { id: 'power', label: 'Произвол ханских чиновников', role: 'cause', kind: 'political', explanation: 'Беки правили жестоко — недовольство росло.' },
          { id: 'raid', label: 'Карательный поход на кочевья', role: 'trigger', kind: 'political', explanation: 'Этот случай лишь запустил восстание — это повод.' },
          { id: 'weak', label: 'Ослабление власти хана', role: 'consequence', term: 'long', explanation: 'Восстания подрывали ханство изнутри.' },
          { id: 'tea', label: 'Мода на чай в Европе', role: 'unrelated', explanation: 'Никак не связано с событиями в ханстве.' },
        ],
        explanation: 'Причины готовили восстание долго, повод его запустил, а последствия ослабили ханство.',
      },
    },
  },
  'chronology-line': {
    usage: 'Для истории: хронология событий, а также этапы открытий в других предметах.',
    interaction: 'Перетащите карточки на свои годы (или введите год) и проверьте — лента покажет, на сколько вы ошиблись.',
    block: {
      component: 'ChronologyLine',
      content: {
        title: 'Кыргызстан и Кокандское ханство',
        instruction: 'Расставьте события на ленте времени.',
        events: [
          { id: 'kokand', label: 'Образование Кокандского ханства', year: 1709, explanation: 'Ханство возникло в Ферганской долине и вскоре начало борьбу за земли соседей.' },
          { id: 'south', label: 'Начало походов на Южный Кыргызстан', year: 1762, explanation: 'После разгрома Джунгарии коканские правители начали захват пограничных земель.' },
          { id: 'embassy', label: 'Кыргызское посольство в Россию', year: 1814, explanation: 'Кыргызские бии искали поддержки против Коканда.' },
          { id: 'annex', label: 'Упразднение Кокандского ханства', year: 1876, explanation: 'Россия присоединила территорию ханства, включая южные районы Кыргызстана.' },
        ],
        explanation: 'Порядок: ханство возникает → расширяется на кыргызские земли → бии ищут союзников → ханство упразднено.',
      },
    },
  },
  'generated-media': {
    usage: 'Когда теме нужна наглядная AI-картинка или короткая видео-визуализация: строение клетки, атом, цикл воды, ход эксперимента.',
    interaction: 'Изучите изображение или запустите видео, затем обсудите, какие элементы помогают понять процесс.',
    block: {
      component: 'GeneratedMedia',
      content: {
        title: 'Визуализация строения клетки',
        description: 'Пример медиа-блока, который учитель создаёт через OpenRouter и вставляет в урок.',
        media_kind: 'image',
        data_url: 'data:image/svg+xml;base64,PHN2ZyB2aWV3Qm94PSIwIDAgNTIwIDI4MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iNTIwIiBoZWlnaHQ9IjI4MCIgcng9IjI0IiBmaWxsPSIjZjhmYWZjIi8+PGVsbGlwc2UgY3g9IjI2MCIgY3k9IjE0MCIgcng9IjIwMCIgcnk9IjkwIiBmaWxsPSIjZGNmY2U3IiBzdHJva2U9IiMxNmEzNGEiIHN0cm9rZS13aWR0aD0iNiIvPjxjaXJjbGUgY3g9IjIyMCIgY3k9IjEzNSIgcj0iNDYiIGZpbGw9IiNiZmRiZmUiIHN0cm9rZT0iIzI1NjNlYiIgc3Ryb2tlLXdpZHRoPSI1Ii8+PGVsbGlwc2UgY3g9IjM0MCIgY3k9IjE1NSIgcng9IjQ0IiByeT0iMjAiIGZpbGw9IiNmZWQ3YWEiIHN0cm9rZT0iI2VhNTgwYyIgc3Ryb2tlLXdpZHRoPSI1Ii8+PHRleHQgeD0iMjIwIiB5PSIxNDIiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZvbnQtc2l6ZT0iMTYiIGZvbnQtZmFtaWx5PSJzYW5zLXNlcmlmIiBmaWxsPSIjMWUzYThhIj7Qr9C00YDQvjwvdGV4dD48dGV4dCB4PSIzNDAiIHk9IjE2MCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZm9udC1zaXplPSIxNCIgZm9udC1mYW1pbHk9InNhbnMtc2VyaWYiIGZpbGw9IiM5YTM0MTIiPtCc0LjRgtC+0YXRjTwvdGV4dD48L3N2Zz4=',
        alt_text: 'Схема клетки с подписями',
        caption: 'OpenRouter media API возвращает изображение, а приложение хранит его как блок урока.',
      },
    },
  },
};

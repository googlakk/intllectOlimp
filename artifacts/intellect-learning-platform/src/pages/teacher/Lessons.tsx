import { CreateCourse } from '@/features/teacherLessons/CreateCourse';
import { GardenLessonCard } from '@/features/visualLesson/GardenLessonCard';
import { useState } from 'react';
import { useSubjects } from '@/lib/api';
import { NoSubjectSelected, SectionsList, SubjectPicker } from '@/features/teacherLessons/listViews';
import { KtpImportButton } from '@/features/teacherLessons/KtpImport';
import { subjectGrades, subjectsForGrade } from '@/features/teacherLessons/listModel';
import { CurriculumGraphPanel } from '@/features/teacherLessons/CurriculumGraphPanel';
import { useAuth } from '@/components/auth/AuthContext';

export default function Lessons() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const { data: subjects, isLoading: loadingSubs, error, refetch } = useSubjects();
  const [selectedSubject, setSelectedSubject] = useState<number | null>(() => Number(sessionStorage.getItem('teacher-subject')) || null);
  const [selectedGrade, setSelectedGrade] = useState<number | null>(() => Number(sessionStorage.getItem('teacher-grade')) || null);
  const grades = subjectGrades(subjects);
  const activeGrade = selectedGrade !== null && grades.includes(selectedGrade) ? selectedGrade : grades[0] ?? null;
  const visibleSubjects = subjectsForGrade(subjects, activeGrade);
  const activeSubject = visibleSubjects?.some(subject => subject.id === selectedSubject) ? selectedSubject : null;

  const selectGrade = (grade: number) => {
    sessionStorage.setItem('teacher-grade', String(grade));
    sessionStorage.removeItem('teacher-subject');
    setSelectedGrade(grade);
    setSelectedSubject(null);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Управление уроками</h1>
          <p className="text-muted-foreground mt-2 font-medium">{isAdmin ? 'Редактируйте материалы и структуру курсов' : 'Создавайте и проверяйте уроки по назначенным темам программы'}</p>
        </div>
        {isAdmin && <div className="flex flex-wrap gap-3"><CreateCourse onCreated={(id, grade) => {
          setSelectedSubject(id); setSelectedGrade(grade);
          sessionStorage.setItem('teacher-subject', String(id)); sessionStorage.setItem('teacher-grade', String(grade));
        }} /><KtpImportButton /></div>}
      </div>

      <GardenLessonCard />
      {error && <p role="alert" className="text-destructive">Не удалось загрузить предметы. <button onClick={() => refetch()} className="underline">Повторить</button></p>}
      {!loadingSubs && !error && !subjects?.length && <p className="rounded-xl border bg-card p-6 text-muted-foreground">{isAdmin ? 'Создайте курс или загрузите КТП.' : 'Пока нет назначенных предметов. Администратор должен выбрать для вас предметы и классы программы.'}</p>}
      {grades.length > 0 && (
        <div className="flex items-center gap-2 overflow-x-auto border-b border-border pb-3" aria-label="Класс программы">
          <span className="mr-2 shrink-0 text-sm font-semibold text-muted-foreground">Класс</span>
          {grades.map((grade) => (
            <button
              key={grade}
              type="button"
              onClick={() => selectGrade(grade)}
              aria-pressed={activeGrade === grade}
              className={`h-10 min-w-12 shrink-0 border px-4 text-sm font-bold transition-colors ${
                activeGrade === grade
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground'
              }`}
            >
              {grade}
            </button>
          ))}
        </div>
      )}

      <SubjectPicker
        isLoading={loadingSubs}
        selectedSubject={activeSubject}
        canManage={isAdmin}
        subjects={visibleSubjects}
        onSelect={id => { setSelectedSubject(id); sessionStorage.setItem('teacher-subject', String(id)); }}
      />

      {activeSubject && <SectionsList subjectId={activeSubject} canManage={isAdmin} />}
      {activeSubject && isAdmin && <CurriculumGraphPanel subjectId={activeSubject} />}
      {!activeSubject && visibleSubjects.length > 0 && (
        <NoSubjectSelected />
      )}
    </div>
  );
}

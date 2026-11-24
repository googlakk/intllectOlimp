export default function AdminHome() {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-bold text-foreground">Администрирование</h1>
      <p className="text-muted-foreground">
        Здесь появятся классы, ученики, учителя и предметы. Пока пароли выдаются командой
        <code className="mx-1 rounded bg-muted px-1.5 py-0.5 text-sm">python manage.py set-password &lt;логин&gt;</code>.
      </p>
    </div>
  );
}

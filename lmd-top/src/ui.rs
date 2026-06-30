//! ratatui 렌더링 — 헤더/탭/본문(뷰별)/footer.

use crate::app::{App, View};
use crate::collect::{AccelKind, Snapshot};
use ratatui::prelude::*;
use ratatui::widgets::{Block, Borders, Cell, Paragraph, Row, Sparkline, Table, Tabs};

const C_OK: Color = Color::Green;
const C_WARN: Color = Color::Yellow;
const C_BAD: Color = Color::Red;
const C_DIM: Color = Color::DarkGray;

pub fn draw(f: &mut Frame, app: &App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1), // title
            Constraint::Length(1), // summary
            Constraint::Length(1), // tabs
            Constraint::Min(3),    // body
            Constraint::Length(1), // footer
        ])
        .split(f.area());

    title_bar(f, chunks[0], &app.snap);
    summary_bar(f, chunks[1], &app.snap);
    tabs(f, chunks[2], app);
    match app.view {
        View::Overview => view_overview(f, chunks[3], app),
        View::Accel => view_accel(f, chunks[3], app),
        View::Models => view_models(f, chunks[3], app),
        View::Epp => view_epp(f, chunks[3], app),
        View::Routing => view_routing(f, chunks[3], app),
        View::Pods => view_pods(f, chunks[3], app),
    }
    footer(f, chunks[4], app);
}

fn title_bar(f: &mut Frame, area: Rect, s: &Snapshot) {
    let gw = if s.gw_addr.is_empty() {
        Span::styled("gw —", Style::default().fg(C_DIM))
    } else if s.gw_ok {
        Span::styled(format!("gw {} ●", s.gw_addr), Style::default().fg(C_OK))
    } else {
        Span::styled(format!("gw {} ○", s.gw_addr), Style::default().fg(C_WARN))
    };
    let line = Line::from(vec![
        Span::styled("lmd-top", Style::default().fg(Color::Cyan).add_modifier(Modifier::BOLD)),
        Span::raw(" · llm-d · "),
        Span::raw(format!("{} nodes · ", s.nodes.len())),
        gw,
    ]);
    f.render_widget(Paragraph::new(line), area);
}

fn summary_bar(f: &mut Frame, area: Rect, s: &Snapshot) {
    let (mut gpu, mut rbln, mut rngd, mut busy) = (0, 0, 0, 0);
    for a in &s.accel {
        match a.kind {
            AccelKind::Gpu => gpu += 1,
            AccelKind::Rbln => rbln += 1,
            AccelKind::Rngd => rngd += 1,
        }
        if a.util > 5.0 {
            busy += 1;
        }
    }
    let serving = s.models.iter().filter(|m| m.ready > 0).count();
    let power: f64 = s.accel.iter().map(|a| a.power).sum();
    let line = Line::from(vec![
        Span::styled(format!("A100 {} ", gpu), Style::default().fg(if gpu == 0 { C_DIM } else { C_OK })),
        Span::styled(format!("RBLN {} ", rbln), Style::default().fg(C_OK)),
        Span::styled(format!("RNGD {} ", rngd), Style::default().fg(C_OK)),
        Span::styled(format!("· {} busy ", busy), Style::default().fg(C_DIM)),
        Span::raw("│ "),
        Span::styled(
            format!("models {}/{} ", serving, s.models.len()),
            Style::default().fg(if serving == 0 { C_WARN } else { C_OK }),
        ),
        Span::styled(format!("│ ⚡{:.0}W", power), Style::default().fg(C_DIM)),
    ]);
    f.render_widget(Paragraph::new(line), area);
}

fn tabs(f: &mut Frame, area: Rect, app: &App) {
    let titles: Vec<Line> = View::ALL
        .iter()
        .enumerate()
        .map(|(i, v)| Line::from(format!("{}:{}", i, v.title())))
        .collect();
    let t = Tabs::new(titles)
        .select(app.view.idx())
        .style(Style::default().fg(C_DIM))
        .highlight_style(Style::default().fg(Color::White).add_modifier(Modifier::BOLD | Modifier::REVERSED))
        .divider(" ");
    f.render_widget(t, area);
}

fn footer(f: &mut Frame, area: Rect, app: &App) {
    let txt = if let Some(t) = &app.toast {
        Span::styled(format!(" {} ", t), Style::default().fg(Color::Black).bg(C_WARN))
    } else {
        Span::styled(
            "↑↓ select  Tab next  0-5 view  s scale  q quit",
            Style::default().fg(C_DIM),
        )
    };
    f.render_widget(Paragraph::new(Line::from(txt)), area);
}

// ---------- helpers ----------

fn bar(pct: f64, width: usize) -> String {
    let p = pct.clamp(0.0, 100.0) / 100.0;
    let filled = (p * width as f64).round() as usize;
    let mut s = String::new();
    for i in 0..width {
        s.push(if i < filled { '█' } else { '░' });
    }
    s
}

fn util_color(pct: f64) -> Color {
    if pct > 80.0 {
        C_BAD
    } else if pct > 40.0 {
        C_WARN
    } else if pct > 1.0 {
        C_OK
    } else {
        C_DIM
    }
}

fn fmt_opt(v: Option<f64>) -> String {
    match v {
        Some(x) if !x.is_nan() => format!("{:.0}", x),
        _ => "–".into(),
    }
}
fn fmt_nan(v: f64, dec: usize) -> String {
    if v.is_nan() {
        "–".into()
    } else {
        format!("{:.*}", dec, v)
    }
}

fn block(title: &str) -> Block<'static> {
    Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(C_DIM))
        .title(Span::styled(
            format!(" {} ", title),
            Style::default().fg(Color::Cyan),
        ))
}

// ---------- views ----------

fn view_accel(f: &mut Frame, area: Rect, app: &App) {
    let rows: Vec<Row> = app
        .snap
        .accel
        .iter()
        .enumerate()
        .map(|(i, a)| {
            let cells = vec![
                Cell::from(a.kind.label()),
                Cell::from(a.id.clone()),
                Cell::from(a.node.clone()),
                Cell::from(Span::styled(
                    format!("{} {:>3.0}%", bar(a.util, 10), a.util),
                    Style::default().fg(util_color(a.util)),
                )),
                Cell::from(format!("{:.0}/{:.0}G", a.mem_used_gb, a.mem_total_gb)),
                Cell::from(format!("{:.0}°C", a.temp)),
                Cell::from(format!("{:.0}W", a.power)),
                Cell::from(Span::styled(trunc(&a.busy_model, 22), Style::default().fg(C_DIM))),
            ];
            let mut r = Row::new(cells);
            if i == app.selected {
                r = r.style(Style::default().add_modifier(Modifier::REVERSED));
            }
            r
        })
        .collect();
    let widths = [
        Constraint::Length(5),
        Constraint::Length(6),
        Constraint::Length(16),
        Constraint::Length(16),
        Constraint::Length(9),
        Constraint::Length(6),
        Constraint::Length(6),
        Constraint::Min(10),
    ];
    let table = Table::new(rows, widths)
        .header(hrow(&["KIND", "ID", "NODE", "UTIL", "MEM", "TEMP", "PWR", "MODEL/POD"]))
        .block(block("Accelerators (NVIDIA / RBLN / Furiosa)"));

    // 하단에 선택된 가속기 스파크라인
    let split = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(3), Constraint::Length(3)])
        .split(area);
    f.render_widget(table, split[0]);

    if let Some(a) = app.snap.accel.get(app.selected) {
        let key = format!("{}:{}:{}", a.kind.label(), a.node, a.id);
        let data = app.hist_for(&key);
        let spark = Sparkline::default()
            .block(block(&format!("util history · {} {}", a.kind.label(), a.id)))
            .data(&data)
            .max(100)
            .style(Style::default().fg(util_color(a.util)));
        f.render_widget(spark, split[1]);
    }
}

fn view_models(f: &mut Frame, area: Rect, app: &App) {
    f.render_widget(models_table(app, "Models (deployments + vLLM)"), area);
}

fn models_table<'a>(app: &'a App, title: &'a str) -> Table<'a> {
    let rows: Vec<Row> = app
        .snap
        .models
        .iter()
        .enumerate()
        .map(|(i, m)| {
            let color = if m.status.contains("Running") {
                C_OK
            } else if m.status.contains("Pending") {
                C_WARN
            } else {
                C_DIM
            };
            let cells = vec![
                Cell::from(trunc(&m.name, 22)),
                Cell::from(format!("{}/{}", m.ready, m.desired)),
                Cell::from(fmt_opt(m.running)),
                Cell::from(fmt_opt(m.waiting)),
                Cell::from(m.tps.map(|x| format!("{:.0}", x)).unwrap_or("–".into())),
                Cell::from(if m.route.is_empty() { "–".into() } else { m.route.clone() }),
                Cell::from(Span::styled(m.status.clone(), Style::default().fg(color))),
            ];
            let mut r = Row::new(cells);
            if i == app.selected {
                r = r.style(Style::default().add_modifier(Modifier::REVERSED));
            }
            r
        })
        .collect();
    let widths = [
        Constraint::Length(22),
        Constraint::Length(7),
        Constraint::Length(5),
        Constraint::Length(5),
        Constraint::Length(6),
        Constraint::Length(12),
        Constraint::Min(12),
    ];
    Table::new(rows, widths)
        .header(hrow(&["MODEL", "READY", "RUN", "WAIT", "t/s", "PATH", "STATUS"]))
        .block(block(title))
}

fn view_pods(f: &mut Frame, area: Rect, app: &App) {
    let rows: Vec<Row> = app
        .snap
        .pods
        .iter()
        .enumerate()
        .map(|(i, p)| {
            let color = match p.phase.as_str() {
                "Running" => C_OK,
                "Pending" => C_WARN,
                "Failed" => C_BAD,
                _ => C_DIM,
            };
            let cells = vec![
                Cell::from(trunc(&p.name, 38)),
                Cell::from(p.ready.clone()),
                Cell::from(Span::styled(p.phase.clone(), Style::default().fg(color))),
                Cell::from(p.node.clone()),
                Cell::from(p.restarts.to_string()),
            ];
            let mut r = Row::new(cells);
            if i == app.selected {
                r = r.style(Style::default().add_modifier(Modifier::REVERSED));
            }
            r
        })
        .collect();
    let widths = [
        Constraint::Min(20),
        Constraint::Length(6),
        Constraint::Length(10),
        Constraint::Length(18),
        Constraint::Length(8),
    ];
    let t = Table::new(rows, widths)
        .header(hrow(&["POD", "READY", "PHASE", "NODE", "RESTARTS"]))
        .block(block("Pods (llm-serving)"));
    f.render_widget(t, area);
}

fn view_epp(f: &mut Frame, area: Rect, app: &App) {
    let split = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(5), Constraint::Length(6)])
        .split(area);

    // scorers
    let mut lines: Vec<Line> = Vec::new();
    match &app.snap.epp {
        Some(cfg) => {
            lines.push(Line::from(vec![
                Span::styled("profile: ", Style::default().fg(C_DIM)),
                Span::styled(cfg.profile.clone(), Style::default().fg(Color::White)),
                Span::raw("   picker: "),
                Span::styled(cfg.picker.clone(), Style::default().fg(Color::White)),
            ]));
            lines.push(Line::from(""));
            let maxw = cfg.scorers.iter().map(|(_, w)| *w).fold(1.0, f64::max);
            for (name, w) in &cfg.scorers {
                let bw = ((w / maxw) * 14.0).round() as usize;
                lines.push(Line::from(vec![
                    Span::styled(format!("{:<32}", name), Style::default().fg(Color::White)),
                    Span::styled(format!("w{:>2.0} ", w), Style::default().fg(C_WARN)),
                    Span::styled("█".repeat(bw), Style::default().fg(Color::Cyan)),
                ]));
            }
        }
        None => lines.push(Line::from(Span::styled(
            "EPP ConfigMap 미발견 (llmd-router-epp)",
            Style::default().fg(C_DIM),
        ))),
    }
    f.render_widget(
        Paragraph::new(lines).block(block("EPP Inspector · active scorers (ConfigMap)")),
        split[0],
    );

    // pools
    let rows: Vec<Row> = app
        .snap
        .pools
        .iter()
        .map(|p| {
            Row::new(vec![
                Cell::from(p.name.clone()),
                Cell::from(format!("{:.0}", p.ready)),
                Cell::from(fmt_nan(p.queue, 1)),
                Cell::from(fmt_nan(p.kv, 2)),
                Cell::from(fmt_nan(p.sat, 2)),
            ])
        })
        .collect();
    let t = Table::new(
        rows,
        [
            Constraint::Min(16),
            Constraint::Length(8),
            Constraint::Length(10),
            Constraint::Length(8),
            Constraint::Length(8),
        ],
    )
    .header(hrow(&["POOL", "READY", "QUEUEavg", "KV", "SAT"]))
    .block(block("InferencePool 상태"));
    f.render_widget(t, split[1]);
}

fn view_routing(f: &mut Frame, area: Rect, app: &App) {
    let mut lines: Vec<Line> = Vec::new();
    let gw = if app.snap.gw_addr.is_empty() {
        "llm-d-gateway (—)".to_string()
    } else {
        format!(
            "llm-d-gateway ({} {})",
            app.snap.gw_addr,
            if app.snap.gw_ok { "●" } else { "○" }
        )
    };
    lines.push(Line::from(Span::styled(gw, Style::default().fg(C_OK))));
    if app.snap.routes.is_empty() {
        lines.push(Line::from(Span::styled("  (no HTTPRoute)", Style::default().fg(C_DIM))));
    }
    for (i, (path, backend)) in app.snap.routes.iter().enumerate() {
        let branch = if i + 1 == app.snap.routes.len() { "└─" } else { "├─" };
        lines.push(Line::from(vec![
            Span::styled(format!(" {} ", branch), Style::default().fg(C_DIM)),
            Span::styled(format!("{:<8}", path), Style::default().fg(Color::White)),
            Span::raw(" → "),
            Span::styled(backend.clone(), Style::default().fg(Color::Cyan)),
        ]));
    }
    f.render_widget(
        Paragraph::new(lines).block(block("Routing · Gateway → HTTPRoute → backend")),
        area,
    );
}

fn view_overview(f: &mut Frame, area: Rect, app: &App) {
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(8), // accel
            Constraint::Length(5), // pools
            Constraint::Min(4),    // models
            Constraint::Length(3), // diagnosis
        ])
        .split(area);

    // accel 요약 (간단 라인)
    let mut al: Vec<Line> = Vec::new();
    for a in app.snap.accel.iter().take(10) {
        al.push(Line::from(vec![
            Span::styled(format!("{:<5}", a.kind.label()), Style::default().fg(Color::White)),
            Span::styled(format!("{:<6}", a.id), Style::default().fg(C_DIM)),
            Span::styled(
                format!("{} {:>3.0}% ", bar(a.util, 8), a.util),
                Style::default().fg(util_color(a.util)),
            ),
            Span::styled(format!("{:.0}°C {:.0}W ", a.temp, a.power), Style::default().fg(C_DIM)),
            Span::styled(trunc(&a.busy_model, 20), Style::default().fg(C_DIM)),
        ]));
    }
    if al.is_empty() {
        al.push(Line::from(Span::styled("  (no accelerator metrics)", Style::default().fg(C_DIM))));
    }
    f.render_widget(Paragraph::new(al).block(block("Accelerators")), rows[0]);

    // pools
    let mut pl: Vec<Line> = Vec::new();
    for p in &app.snap.pools {
        pl.push(Line::from(format!(
            " {:<16} ready {:.0}  queue {}  kv {}  sat {}",
            p.name,
            p.ready,
            fmt_nan(p.queue, 1),
            fmt_nan(p.kv, 2),
            fmt_nan(p.sat, 2)
        )));
    }
    if let Some(cfg) = &app.snap.epp {
        let names: Vec<String> = cfg.scorers.iter().map(|(n, w)| format!("{}·{:.0}", n.replace("-scorer", ""), w)).collect();
        pl.push(Line::from(Span::styled(
            format!(" scorers: {}", names.join("  ")),
            Style::default().fg(C_DIM),
        )));
    }
    if pl.is_empty() {
        pl.push(Line::from(Span::styled("  (no InferencePool)", Style::default().fg(C_DIM))));
    }
    f.render_widget(Paragraph::new(pl).block(block("Inference (EPP pools)")), rows[1]);

    // models
    f.render_widget(models_table(app, "Models"), rows[2]);

    // diagnosis
    let diag = diagnose(&app.snap);
    f.render_widget(
        Paragraph::new(Line::from(Span::styled(diag.0, Style::default().fg(diag.1))))
            .block(block("Diagnosis")),
        rows[3],
    );
}

/// cross-layer 1줄 진단 (M6 규칙엔진 v1).
fn diagnose(s: &Snapshot) -> (String, Color) {
    let serving = s.models.iter().filter(|m| m.ready > 0).count();
    if s.accel.is_empty() && serving == 0 {
        return ("⚠ 가속기 메트릭 없음 + 서빙 모델 없음 — Prometheus/모델 상태 점검".into(), C_BAD);
    }
    if serving == 0 {
        return ("⚠ 서빙 중인 모델 0 — 'n' 런처 또는 Models 뷰 's'로 기동 (백엔드 없음)".into(), C_WARN);
    }
    let busy = s.accel.iter().filter(|a| a.util > 80.0).count();
    if busy > 0 {
        return (format!("● {} 모델 서빙 중, 가속기 {}개 고부하(>80%)", serving, busy), C_OK);
    }
    (format!("● {} 모델 서빙 중, 가속기 여유", serving), C_OK)
}

fn hrow(cols: &[&str]) -> Row<'static> {
    Row::new(
        cols.iter()
            .map(|c| Cell::from(Span::styled(c.to_string(), Style::default().fg(C_DIM).add_modifier(Modifier::BOLD))))
            .collect::<Vec<_>>(),
    )
}

fn trunc(s: &str, n: usize) -> String {
    if s.chars().count() <= n {
        s.to_string()
    } else {
        let t: String = s.chars().take(n.saturating_sub(1)).collect();
        format!("{}…", t)
    }
}

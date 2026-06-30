//! UI 상태머신 — 현재 뷰, 선택, 스파크라인 히스토리. 데이터(Snapshot)와 분리.

use crate::collect::Snapshot;
use std::collections::{HashMap, VecDeque};

#[derive(Clone, Copy, PartialEq)]
pub enum View {
    Overview,
    Accel,
    Models,
    Epp,
    Routing,
    Pods,
}

impl View {
    pub const ALL: [View; 6] = [
        View::Overview,
        View::Accel,
        View::Models,
        View::Epp,
        View::Routing,
        View::Pods,
    ];
    pub fn idx(&self) -> usize {
        View::ALL.iter().position(|v| v == self).unwrap_or(0)
    }
    pub fn title(&self) -> &'static str {
        match self {
            View::Overview => "Overview",
            View::Accel => "Accel",
            View::Models => "Models",
            View::Epp => "EPP",
            View::Routing => "Route",
            View::Pods => "Pods",
        }
    }
}

pub const HIST: usize = 40;

pub struct App {
    pub view: View,
    pub selected: usize,
    pub snap: Snapshot,
    pub hist: HashMap<String, VecDeque<u64>>, // accel util 히스토리
    pub toast: Option<String>,
    pub should_quit: bool,
}

impl App {
    pub fn new() -> Self {
        App {
            view: View::Overview,
            selected: 0,
            snap: Snapshot::default(),
            hist: HashMap::new(),
            toast: None,
            should_quit: false,
        }
    }

    /// 새 스냅샷 반영 + ts 가 바뀌었으면 히스토리 append.
    pub fn apply(&mut self, snap: Snapshot) {
        if snap.ts != self.snap.ts {
            for a in &snap.accel {
                let key = format!("{}:{}:{}", a.kind.label(), a.node, a.id);
                let buf = self.hist.entry(key).or_default();
                buf.push_back(a.util.round().clamp(0.0, 100.0) as u64);
                while buf.len() > HIST {
                    buf.pop_front();
                }
            }
        }
        self.snap = snap;
        let n = self.list_len();
        if n > 0 && self.selected >= n {
            self.selected = n - 1;
        }
    }

    pub fn hist_for(&self, key: &str) -> Vec<u64> {
        self.hist
            .get(key)
            .map(|d| d.iter().copied().collect())
            .unwrap_or_default()
    }

    pub fn set_view_idx(&mut self, i: usize) {
        if i < View::ALL.len() {
            self.view = View::ALL[i];
            self.selected = 0;
        }
    }

    pub fn next_tab(&mut self) {
        self.set_view_idx((self.view.idx() + 1) % View::ALL.len());
    }

    /// 현재 뷰에서 선택 가능한 행 수.
    pub fn list_len(&self) -> usize {
        match self.view {
            View::Models | View::Overview => self.snap.models.len(),
            View::Pods => self.snap.pods.len(),
            View::Accel => self.snap.accel.len(),
            _ => 0,
        }
    }

    pub fn move_sel(&mut self, delta: i64) {
        let n = self.list_len();
        if n == 0 {
            return;
        }
        let cur = self.selected as i64 + delta;
        self.selected = cur.rem_euclid(n as i64) as usize;
    }

    /// Models/Overview 뷰에서 선택된 모델(scale 대상).
    pub fn selected_model(&self) -> Option<&crate::collect::ModelRow> {
        match self.view {
            View::Models | View::Overview => self.snap.models.get(self.selected),
            _ => None,
        }
    }
}

/** DSH-specific same-process service wiring for the fresh, no-tool owner.
 * Mount stock BasicCompaction auto:false before attaching. The embedding owner
 * serializes calls; no alternate writer, global freeze or restart is covered.
 * Transport to Python, if needed, belongs to that embedding host.
 */
export class DshNativeHost {
  constructor(ctx, agent, { version, createUserMessage }) {
    if (version !== '0.2.0-rc.2' || agent.session.seq !== 0) {
      throw new Error('DSH host requires the pinned fresh Session');
    }
    this.ctx = ctx;
    this.agent = agent;
    this.version = version;
    this.createUserMessage = createUserMessage;
    this.session_id = agent.id;
    this.events = [];
    this.workCount = this.requestCount = 0;
    this.stopped = false;
    this.dispose = ctx.on('session/event', (session, event) => {
      if (session.id === this.session_id) {
        this.events.push(structuredClone({ sessionId: session.id, ...event }));
      }
    });
  }

  async observe() {
    if (this.stopped) throw new Error('DSH owner stopped; no retry');
    await this.agent.whenIdle();
    const a = this.agent;
    return {
      sessionId: a.id, seq: a.session.seq, settled: true, status: a.status,
      nextTurn: a.inbox.nextTurn.map(x => x.id),
      nextStep: a.inbox.nextStep.map(x => x.id),
      lastTurnEnd: this.events.findLast(e => e.type === 'turn/end')?.data ?? {},
    };
  }

  async work(prompt) {
    const before = await this.observe();
    if (this.workCount || this.requestCount || before.status !== 'idle'
        || before.nextTurn.length || before.nextStep.length) {
      throw new Error('DSH profile allows one foreground turn');
    }
    this.workCount = 1;
    try {
      this.agent.followup(this.createUserMessage({
        content: [{ type: 'text', text: prompt }], source: { kind: 'user' },
      }));
      return await this.observe();
    } catch (error) {
      this.stopped = true;
      throw error;
    }
  }

  async compact(requestSeq, preSeq) {
    const before = await this.observe();
    if (this.requestCount || requestSeq !== 1 || this.workCount !== 1
        || preSeq !== before.seq || before.status !== 'idle'
        || before.nextTurn.length || before.nextStep.length) {
      throw new Error('DSH native request is stale, busy or already consumed');
    }
    this.requestCount = 1;
    try {
      // Native runMaintenance reserves the owned idle driver and queued input.
      const result = await this.ctx.compaction.compactNow(
        this.agent, new AbortController().signal);
      if (!result) throw new Error('DSH produced no native transition');
      const events = this.events.filter(e => e.seq >= preSeq && (
        e.type.startsWith('compaction/')
        || e.data?.source?.kind === 'compact-checkpoint'));
      await this.ctx.sessions.flush(this.agent.session);
      const handle = await this.ctx.sessionPersistence.open(this.session_id, 'read');
      let readback;
      try { readback = await handle.read(); }
      finally { await handle.close(); }
      return structuredClone({
        requestSeq, preSeq, result, events, flushed: true,
        readbackSessionId: this.session_id, readbackEvents: readback.events,
      });
    } catch (error) {
      this.stopped = true;
      throw error;
    }
  }

  async project() {
    const current = await this.observe();
    return structuredClone({ sessionId: current.sessionId, seq: current.seq,
      messages: this.agent.session.deriveMessages() });
  }
}

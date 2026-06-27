/** Reference-counted room membership. Emits subscribe on 0→1 and unsubscribe on 1→0,
 * so overlapping subscribers (e.g. the board's active workstream and My Work's set)
 * never tear down a room another consumer still needs. */
export class RoomRefs {
	private refs = new Map<string, number>();
	constructor(
		private onSubscribe: (key: string) => void,
		private onUnsubscribe: (key: string) => void
	) {}

	enter(key: string): void {
		const n = (this.refs.get(key) ?? 0) + 1;
		this.refs.set(key, n);
		if (n === 1) this.onSubscribe(key);
	}

	leave(key: string): void {
		const cur = this.refs.get(key);
		if (!cur) return;
		if (cur <= 1) {
			this.refs.delete(key);
			this.onUnsubscribe(key);
		} else {
			this.refs.set(key, cur - 1);
		}
	}

	keys(): string[] {
		return [...this.refs.keys()];
	}
}

/**
 * GremlinBenchRN — a deliberately broken React Native app.
 *
 * This is a *fixture*, not a product: every screen below contains one planted
 * defect that makes the framework confess a specific failure to `adb logcat`.
 * Gremlin's claim is that detection needs no model judgment because the toolkit
 * reports its own breakage, and this app is how that claim gets tested — each
 * bug here has a known, exact log signature the oracle must find.
 *
 * Navigation is hand-rolled state rather than react-navigation, so the fixture
 * has no dependency that could itself be the thing that breaks.
 *
 * Screens are reachable by a single tap from Home, because Gremlin explores by
 * tapping and a defect behind a five-step flow tests the explorer, not the
 * oracle.
 */

import React, {useEffect, useState} from 'react';
import {
  FlatList,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import {SafeAreaProvider, SafeAreaView} from 'react-native-safe-area-context';

type ScreenName = 'home' | 'crash' | 'keys' | 'async' | 'hook' | 'clean';

const SCREENS: {id: ScreenName; label: string; blurb: string}[] = [
  {id: 'crash', label: 'Null Crash', blurb: 'reads a property of undefined'},
  {id: 'keys', label: 'Missing Keys', blurb: 'list rendered without key props'},
  {id: 'async', label: 'Bad Fetch', blurb: 'unhandled promise rejection'},
  {id: 'hook', label: 'Late setState', blurb: 'state update after unmount'},
  {id: 'clean', label: 'Healthy Screen', blurb: 'no defect — must stay silent'},
];

export default function App() {
  const [screen, setScreen] = useState<ScreenName>('home');

  return (
    <SafeAreaProvider>
      <StatusBar barStyle="light-content" backgroundColor="#0b0f0e" />
      <SafeAreaView style={styles.root}>
        {screen === 'home' ? (
          <Home onOpen={setScreen} />
        ) : (
          <Frame onBack={() => setScreen('home')}>
            {screen === 'crash' && <CrashScreen />}
            {screen === 'keys' && <MissingKeysScreen />}
            {screen === 'async' && <BadFetchScreen />}
            {screen === 'hook' && <LateSetStateScreen />}
            {screen === 'clean' && <HealthyScreen />}
          </Frame>
        )}
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

function Home({onOpen}: {onOpen: (s: ScreenName) => void}) {
  return (
    <ScrollView contentContainerStyle={styles.pad}>
      <Text style={styles.h1}>GremlinBench RN</Text>
      <Text style={styles.sub}>Five screens. Four are broken on purpose.</Text>
      {SCREENS.map(s => (
        <TouchableOpacity
          key={s.id}
          style={styles.card}
          accessibilityLabel={s.label}
          onPress={() => onOpen(s.id)}>
          <Text style={styles.cardTitle}>{s.label}</Text>
          <Text style={styles.cardBlurb}>{s.blurb}</Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}

function Frame({
  onBack,
  children,
}: {
  onBack: () => void;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.flex}>
      <TouchableOpacity
        style={styles.back}
        accessibilityLabel="Back"
        onPress={onBack}>
        <Text style={styles.backText}>‹ Back</Text>
      </TouchableOpacity>
      <View style={styles.pad}>{children}</View>
    </View>
  );
}

/* ------------------------------------------------------------------ *
 * Planted defect 1 — js-exception
 * Reading through an undefined object throws a TypeError that escapes
 * render. Expected log: "TypeError: Cannot read property 'name' of
 * undefined", forwarded by the probe as GREMLIN_BUG [fatal].
 * ------------------------------------------------------------------ */
function CrashScreen() {
  const profile: {user?: {name: string}} = {};
  // The optional chain is deliberately missing — this is the bug.
  const name = (profile.user as {name: string}).name;
  return <Text style={styles.body}>Signed in as {name}</Text>;
}

/* ------------------------------------------------------------------ *
 * Planted defect 2 — react-warning
 * A list rendered without `key` props. React logs "Each child in a list
 * should have a unique key prop." This is not a style nit: without keys
 * React reuses the wrong nodes on reorder and silently corrupts state.
 * ------------------------------------------------------------------ */
function MissingKeysScreen() {
  const rows = ['Alpha', 'Bravo', 'Charlie', 'Delta'];
  return (
    <View>
      <Text style={styles.body}>Team roster</Text>
      {rows.map(r => (
        // Intentionally no key={r}.
        <Text style={styles.row}>{r}</Text>
      ))}
    </View>
  );
}

/* ------------------------------------------------------------------ *
 * Planted defect 3 — unhandled-rejection
 * A request whose failure nobody catches. Expected log: "Possible
 * Unhandled Promise Rejection".
 * ------------------------------------------------------------------ */
function BadFetchScreen() {
  const [state] = useState('loading');
  useEffect(() => {
    // No .catch() and no try/await — the rejection escapes.
    fetch('http://127.0.0.1:1/definitely-not-listening').then(r => r.json());
  }, []);
  return <Text style={styles.body}>Loading feed… ({state})</Text>;
}

/* ------------------------------------------------------------------ *
 * Planted defect 4 — react-warning
 * setState fired after the component unmounted, by a timer nobody
 * cleaned up. Classic leak; React warns about the update.
 * ------------------------------------------------------------------ */
function LateSetStateScreen() {
  const [ticks, setTicks] = useState(0);
  useEffect(() => {
    // Deliberately returns no cleanup, so the interval outlives the screen.
    setInterval(() => setTicks(t => t + 1), 400);
  }, []);
  return <Text style={styles.body}>Ticks: {ticks}</Text>;
}

/* ------------------------------------------------------------------ *
 * Control — this screen is correct. If Gremlin reports a bug here, the
 * oracle is producing false positives, which matters more than a miss.
 * ------------------------------------------------------------------ */
function HealthyScreen() {
  const items = [
    {id: '1', label: 'Inbox'},
    {id: '2', label: 'Drafts'},
    {id: '3', label: 'Archive'},
  ];
  return (
    <FlatList
      data={items}
      keyExtractor={i => i.id}
      renderItem={({item}) => <Text style={styles.row}>{item.label}</Text>}
    />
  );
}

const styles = StyleSheet.create({
  root: {flex: 1, backgroundColor: '#0b0f0e'},
  flex: {flex: 1},
  pad: {padding: 20},
  h1: {color: '#5ee6a8', fontSize: 26, fontWeight: '700', marginBottom: 4},
  sub: {color: '#8ea79c', fontSize: 14, marginBottom: 20},
  card: {
    backgroundColor: '#141b19',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#1f2c28',
  },
  cardTitle: {color: '#e8f5ef', fontSize: 17, fontWeight: '600'},
  cardBlurb: {color: '#7d938a', fontSize: 13, marginTop: 3},
  body: {color: '#e8f5ef', fontSize: 16, marginBottom: 10},
  row: {color: '#b9cec5', fontSize: 15, paddingVertical: 6},
  back: {padding: 16},
  backText: {color: '#5ee6a8', fontSize: 16},
});

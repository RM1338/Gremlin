/**
 * @format
 */

// Must come first: the probe installs the global error handler, and anything
// that throws before it is installed would go unreported.
import './gremlinProbe';

import { AppRegistry } from 'react-native';
import App from './App';
import { name as appName } from './app.json';

AppRegistry.registerComponent(appName, () => App);

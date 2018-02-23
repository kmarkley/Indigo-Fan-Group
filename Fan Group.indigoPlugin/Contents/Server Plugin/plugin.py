#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# http://www.indigodomo.com

import indigo
import time
from ghpu import GitHubPluginUpdater

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

###############################################################################
# globals

kSpeedIndex = {
    0:  'off',
    1:  'low',
    2:  'medium',
    3:  'high',
    }

k_updateCheckHours = 24

################################################################################
class Plugin(indigo.PluginBase):
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
        self.updater = GitHubPluginUpdater(self)

    def __del__(self):
        indigo.PluginBase.__del__(self)

    #-------------------------------------------------------------------------------
    # Start, Stop and Config changes
    #-------------------------------------------------------------------------------
    def startup(self):
        self.nextCheck = self.pluginPrefs.get('nextUpdateCheck',0)
        self.debug = self.pluginPrefs.get('showDebugInfo',False)
        self.logger.debug("startup")
        if self.debug:
            self.logger.debug("Debug logging enabled")
        self.deviceDict = dict()
        indigo.devices.subscribeToChanges()

    #-------------------------------------------------------------------------------
    def shutdown(self):
        self.logger.debug("shutdown")
        self.pluginPrefs['nextUpdateCheck'] = self.nextCheck
        self.pluginPrefs['showDebugInfo'] = self.debug

    #-------------------------------------------------------------------------------
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.logger.debug("closedPrefsConfigUi")
        if not userCancelled:
            self.debug = valuesDict.get("showDebugInfo",False)
            if self.debug:
                self.logger.debug("Debug logging enabled")

    #-------------------------------------------------------------------------------
    def runConcurrentThread(self):
        self.logger.debug("runConcurrentThread")
        try:
            while True:
                loopTime = time.time()
                for devId, device in self.deviceDict.items():
                    device.loopAction()
                if loopTime > self.nextCheck:
                    self.checkForUpdates()
                self.sleep(loopTime+10-time.time())
        except self.StopThread:
            pass    # Optionally catch the StopThread exception and do any needed cleanup.

    #-------------------------------------------------------------------------------
    # Device Methods
    #-------------------------------------------------------------------------------
    def deviceStartComm(self, device):
        self.logger.debug("deviceStartComm: "+device.name)

        if device.version != self.pluginVersion:
            self.updateDeviceVersion(device)

        if device.configured:
            if device.deviceTypeId == 'fanGroupSimple':
                self.deviceDict[device.id] = self.GroupRelay(device, self)
            elif device.deviceTypeId == 'fanGroupFull':
                self.deviceDict[device.id] = self.GroupSpeedcontrol(device, self)
            elif device.deviceTypeId == 'thermAssist':
                self.deviceDict[device.id] = self.GroupThermAssist(device, self)
            self.deviceDict[device.id].updateGroup()

    #-------------------------------------------------------------------------------
    def deviceStopComm(self, device):
        self.logger.debug("deviceStopComm: "+device.name)
        if device.id in self.deviceDict:
            del self.deviceDict[device.id]

    #-------------------------------------------------------------------------------
    def validateDeviceConfigUi(self, valuesDict, typeId, devId, runtime=False):
        self.logger.debug("validateDeviceConfigUi: " + typeId)
        errorsDict = indigo.Dict()

        if not valuesDict.get('fans',''):
            errorsDict['fans'] = "Select at least one fan"

        if typeId == 'thermAssist':
            for key in ['onThreshold','offThreshold']:
                if valuesDict.get(key,"") == "":
                    errorsDict[key] = "Required"
                else:
                    try:
                        t = float(valuesDict[key])
                        if t <= 0.0:
                            raise
                    except:
                        errorsDict[key] = "Must be positive real number"
            if not errorsDict:
                if float(valuesDict['offThreshold']) > float(valuesDict['offThreshold']):
                    errorsDict['offThreshold'] = "Must be less than or equal to ON Threshold"

        if len(errorsDict) > 0:
            return (False, valuesDict, errorsDict)
        else:
            return (True, valuesDict)

    #-------------------------------------------------------------------------------
    def updateDeviceVersion(self, device):
        theProps = device.pluginProps
        # update states
        device.stateListOrDisplayStateIdChanged()
        # check for changed props

        # push to server
        theProps["version"] = self.pluginVersion
        device.replacePluginPropsOnServer(theProps)


    #-------------------------------------------------------------------------------
    # Device updated
    #-------------------------------------------------------------------------------
    def deviceUpdated(self, oldDev, newDev):

        # device belongs to plugin
        if newDev.pluginId == self.pluginId or oldDev.pluginId == self.pluginId:
            # update local copy (will be removed/overwritten if communication is stopped/re-started)
            if newDev.id in self.deviceDict:
                self.deviceDict[newDev.id].refresh(newDev)
            indigo.PluginBase.deviceUpdated(self, oldDev, newDev)

        # speedcontrol device
        elif isinstance(newDev, indigo.SpeedControlDevice) and (newDev.speedLevel != oldDev.speedLevel):
            for devId, device in self.deviceDict.items():
                device.fanUpdated(oldDev, newDev)

        # thermostat device
        elif isinstance(newDev, indigo.ThermostatDevice) and (newDev.states != oldDev.states):
            for devId, device in self.deviceDict.items():
                device.thermUpdated(oldDev, newDev)


    #-------------------------------------------------------------------------------
    # Action Methods
    #-------------------------------------------------------------------------------
    def actionControlSpeedControl(self, action, device):
        self.logger.debug("actionControlSpeedControl: "+device.name)
        devGroup = self.deviceDict[device.id]
        # TURN ON
        if action.speedControlAction == indigo.kSpeedControlAction.TurnOn:
            devGroup.turnOn()
        # TURN OFF
        elif action.speedControlAction == indigo.kSpeedControlAction.TurnOff:
            devGroup.turnOff()
        # TOGGLE
        elif action.speedControlAction == indigo.kSpeedControlAction.Toggle:
            devGroup.toggle()
        # SET SPEED INDEX
        elif action.speedControlAction == indigo.kSpeedControlAction.SetSpeedIndex:
            devGroup.setSpeedIndex(action.actionValue)
        # SET SPEED LEVEL
        elif action.speedControlAction == indigo.kSpeedControlAction.SetSpeedLevel:
            devGroup.setSpeedLevel(action.actionValue)
        # INCREASE SPEED INDEX
        elif action.speedControlAction == indigo.kSpeedControlAction.IncreaseSpeedIndex:
            devGroup.increaseSpeedIndex(action.actionValue)
        # DECREASE SPEED INDEX
        elif action.speedControlAction == indigo.kSpeedControlAction.DecreaseSpeedIndex:
            devGroup.decreaseSpeedIndex(action.actionValue)
        # STATUS REQUEST
        elif action.speedControlAction == indigo.kUniversalAction.RequestStatus:
            self.logger.info('"{}" status update'.format(device.name))
            devGroup.updateGroup()
        # UNKNOWN
        else:
            self.logger.error('"{}" {} request ignored'.format(dev.name, unicode(action.speedControlAction)))

    #-------------------------------------------------------------------------------
    def actionControlDimmerRelay(self, action, device):
        self.logger.debug("actionControlDimmerRelay: "+device.name)
        devGroup = self.deviceDict[device.id]
        # TURN ON
        if action.deviceAction == indigo.kSpeedControlAction.TurnOn:
            devGroup.turnOn()
        # TURN OFF
        elif action.deviceAction == indigo.kSpeedControlAction.TurnOff:
            devGroup.turnOff()
        # TOGGLE
        elif action.deviceAction == indigo.kSpeedControlAction.Toggle:
            devGroup.toggle()
        # STATUS REQUEST
        elif action.deviceAction == indigo.kUniversalAction.RequestStatus:
            self.logger.info('"{}" status update'.format(device.name))
            devGroup.updateGroup()
        # UNKNOWN
        else:
            self.logger.debug('"{}" {} request ignored'.format(dev.name, unicode(action.speedControlAction)))

    #-------------------------------------------------------------------------------
    def actionControlSensor(self, action, device):
        self.logger.debug("actionControlSensor: "+device.name)
        devGroup = self.deviceDict[device.id]
        # STATUS REQUEST
        if action.sensorAction == indigo.kUniversalAction.RequestStatus:
            self.logger.info('"{}" status update'.format(device.name))
            devGroup.updateGroup()
        # UNKNOWN
        else:
            self.logger.debug('"{}" {} request ignored'.format(dev.name, unicode(action.speedControlAction)))

    #-------------------------------------------------------------------------------
    # Menu Methods
    #-------------------------------------------------------------------------------
    def checkForUpdates(self):
        try:
            self.updater.checkForUpdate()
        except Exception as e:
            msg = 'Check for update error.  Next attempt in {} hours.'.format(k_updateCheckHours)
            if self.debug:
                self.logger.exception(msg)
            else:
                self.logger.error(msg)
                self.logger.debug(e)
        self.nextCheck = time.time() + k_updateCheckHours*60*60

    #-------------------------------------------------------------------------------
    def updatePlugin(self):
        self.updater.update()

    #-------------------------------------------------------------------------------
    def forceUpdate(self):
        self.updater.update(currentVersion='0.0.0')

    #-------------------------------------------------------------------------------
    def toggleDebug(self):
        if self.debug:
            self.logger.debug("Debug logging disabled")
            self.debug = False
        else:
            self.debug = True
            self.logger.debug("Debug logging enabled")

    #-------------------------------------------------------------------------------
    # Menu Callbacks
    #-------------------------------------------------------------------------------
    def getSpeedControlDeviceList(self, filter="", valuesDict=None, typeId="", targetId=0):
        devList = []
        excludeList  = [dev.id for dev in indigo.devices.iter(filter='self')]
        for dev in indigo.devices.iter(filter='indigo.speedcontrol'):
            if not dev.id in excludeList:
                devList.append((dev.id, dev.name))
        return devList


    ###############################################################################
    # Classes
    ###############################################################################
    class FanGroup(object):

        #-------------------------------------------------------------------------------
        def __init__(self, device, plugin):
            self.plugin     = plugin
            self.logger     = plugin.logger
            self.logger.debug("FanGroup.__init__: {}".format(device.id))

            self.id         = device.id
            self.onLevel    = 0
            self.refresh(device)

            self.fanDict    = dict()
            for fanId in self.props.get('fans',[]):
                self.fanDict[int(fanId)] = plugin.ControlledFan(int(fanId))

        #-------------------------------------------------------------------------------
        # action methods
        #-------------------------------------------------------------------------------
        def turnOn(self):
            self.logger.info('"{}" on'.format(self.name))
            self.setSpeedIndex(self.onLevel)

        #-------------------------------------------------------------------------------
        def turnOff(self):
            self.logger.info('"{}" off'.format(self.name))
            self.setSpeedIndex(0)

        #-------------------------------------------------------------------------------
        def toggle(self):
            if self.onState:
                self.turnOff()
            else:
                self.turnOn()

        #-------------------------------------------------------------------------------
        def setSpeedIndex(self, speedIndex):
            self.logger.info('"{}" set motor speed to {}'.format(self.name, kSpeedIndex[speedIndex]))
            for fanId, fan in self.fanDict.items():
                fan.setSpeedIndex(speedIndex)

        #-------------------------------------------------------------------------------
        def increaseSpeedIndex(self, value):
            self.setSpeedIndex(max(self.speedIndex+value, 3))

        #-------------------------------------------------------------------------------
        def decreaseSpeedIndex(self, value):
            self.setSpeedIndex(min(self.speedIndex-value, 0))

        #-------------------------------------------------------------------------------
        def setSpeedLevel(self, speedLevel):
            self.logger.info('"{}" set motor speed to {}'.format(self.name, speedLevel))
            for fanId, fan in self.fanDict.items():
                fan.setSpeedLevel(speedLevel)

        #-------------------------------------------------------------------------------
        # device updated methods
        #-------------------------------------------------------------------------------
        def refresh(self, device=None):
            if not device:
                device  = indigo.devices[self.id]
            self.logger.debug("FanGroup.refresh: {}".format(device.name))
            self.device = device
            self.name   = device.name
            self.props  = device.pluginProps
            self.states = device.states

        #-------------------------------------------------------------------------------
        def fanUpdated(self, oldDev, newDev):
            if newDev.id in self.fanDict:
                self.logger.debug("FanGroup.fanUpdated: {} ({})".format(self.name, newDev.name))
                self.fanDict[newDev.id].refresh(newDev)
                self.updateGroup()

        #-------------------------------------------------------------------------------
        def updateGroup(self):
            self.logger.debug("FanGroup.updateGroup: "+self.name)
            fanList  = list(fan for fanId, fan in self.fanDict.items())
            self.min = min(fan.speedIndex for fan in fanList)
            self.max = max(fan.speedIndex for fan in fanList)
            self.avg = int(round(float(sum(fan.speedIndex for fan in fanList))/len(fanList)))
            self.any = any(fan.speedLevel > 0 for fan in fanList)
            for speed in range(4):
                if all(fan.speedIndex == speed for fan in fanList):
                    self.all = speed
                    break
                self.all = None
            self.updateState()

        #-------------------------------------------------------------------------------
        # abstract methods
        #-------------------------------------------------------------------------------
        def updateState(self):
            raise NotImplementedError

        #-------------------------------------------------------------------------------
        def thermUpdated(self, oldDev, newDev):
            pass

        #-------------------------------------------------------------------------------
        def loopAction(self):
            pass

    ###############################################################################
    class GroupRelay(FanGroup):

        #-------------------------------------------------------------------------------
        def __init__(self, device, plugin):
            plugin.FanGroup.__init__(self, device, plugin)

            self.logger.debug("GroupRelay.__init__:"+str(device.id))

            self.logic      = self.props['statusLogic']
            self.onLevel    = int(self.props['onLevel'])

        #-------------------------------------------------------------------------------
        def updateState(self):
            self.logger.debug("GroupRelay.updateState: "+self.name)
            if self.logic == "any":
                self.onState = self.any
            elif self.logic == "avg":
                self.onState = self.avg >= self.onLevel
            elif self.logic == "min":
                self.onState = self.min >= self.onLevel
            elif self.logic == "max":
                self.onState = self.max >= self.onLevel
            elif self.logic == "all":
                self.onState = self.all == self.onLevel
            self.device.updateStateOnServer(key='onOffState', value=self.onState)

    ###############################################################################
    class GroupSpeedcontrol(FanGroup):

        #-------------------------------------------------------------------------------
        def __init__(self, device, plugin):
            plugin.FanGroup.__init__(self, device, plugin)

            self.logger.debug("GroupSpeedcontrol.__init__:"+str(device.id))

            self.logic      = self.props.get('statusLogic',"avg")

        #-------------------------------------------------------------------------------
        def updateState(self):
            self.logger.debug("GroupSpeedcontrol.updateState: "+self.name)
            if self.logic == "avg":
                self.speedIndex = self.avg
            elif self.logic == "min":
                self.speedIndex = self.min
            elif self.logic == "max":
                self.speedIndex = self.max
            elif self.logic == "all":
                self.speedIndex = self.all
            self.onstate = self.any
            self.device.updateStateOnServer(key='speedIndex', value=self.speedIndex)

    ###############################################################################
    class GroupThermAssist(FanGroup):

        #-------------------------------------------------------------------------------
        def __init__(self, device, plugin):
            plugin.FanGroup.__init__(self, device, plugin)

            self.logger.debug("GroupThermAssist.__init__:"+str(device.id))

            self.thermId     = int(self.props['thermostat'])
            self.onThresh    = float(self.props['onThreshold'])
            self.offThresh   = float(self.props['offThreshold'])
            self.onLevel     = int(self.props['onLevel'])
            self.onOverride  = self.props['onOverride']
            self.offOverride = self.props['onOverride']
            self.tempFreq    = int(self.props['tempFreq'])
            self.nextTemp    = time.time() + self.tempFreq
            self.therm       = plugin.MonitoredThermostat(self.thermId)
            self.onState     = device.onState

        #-------------------------------------------------------------------------------
        def updateState(self):
            self.logger.debug("GroupThermAssist.updateState: "+self.name)
            coolDelta   = self.therm.temp - self.therm.coolSet
            heatDelta   = self.therm.heatSet - self.therm.temp
            tempDelta   = max([coolDelta,heatDelta])
            onLimit     = tempDelta > self.onThresh
            offLimit    = tempDelta > self.offThresh and self.device.onState
            onFlag      = (self.therm.coolOn or self.therm.heatOn) and (onLimit or offLimit)

            if onFlag and (not self.onState):
                self.onState = True
                self.device.updateStateOnServer(key='onOffState', value=self.onState)
                self.turnOn()
                self.nextTemp = time.time() + self.tempFreq
            elif (not onFlag) and self.onState:
                self.onState = False
                self.device.updateStateOnServer(key='onOffState', value=self.onState)
                self.turnOff()

        #-------------------------------------------------------------------------------
        def thermUpdated(self, oldDev, newDev):
            if newDev.id == self.thermId:
                self.logger.debug("GroupThermAssist.thermUpdated: {} ({})".format(self.name, newDev.name))
                self.therm.refresh(newDev)
                self.updateState()

        #-------------------------------------------------------------------------------
        def loopAction(self):
            if self.onState and self.tempFreq and (self.nextTemp < time.time()):
                self.logger.debug("thermostat status request: "+self.therm.name)
                indigo.device.statusRequest(self.therm.id, suppressLogging=(not self.plugin.debug))
                self.nextTemp = time.time() + self.tempFreq

        #-------------------------------------------------------------------------------
        def setSpeedIndex(self, speedIndex):
            self.logger.info('"{}" set motor speed to {}'.format(self.name, kSpeedIndex[speedIndex]))
            for fanId, fan in self.fanDict.items():
                if (    speedIndex and (self.onOverride or not fan.speedIndex)) or \
                   (not speedIndex and (self.offOverride or    fan.speedIndex == self.onLevel)):
                    fan.setSpeedIndex(speedIndex)

    ###############################################################################
    class ControlledFan(object):

        #-------------------------------------------------------------------------------
        def __init__(self, fanId):
            self.id         = fanId
            self.refresh()

        #-------------------------------------------------------------------------------
        def refresh(self, fan=None):
            if not fan:
                fan = indigo.devices[self.id]
            self.speedIndex = fan.speedIndex
            self.speedLevel = fan.speedLevel

        #-------------------------------------------------------------------------------
        def setSpeedIndex(self, speedIndex):
            if self.speedIndex != speedIndex:
                indigo.speedcontrol.setSpeedIndex(self.id, value=speedIndex)

        #-------------------------------------------------------------------------------
        def setSpeedLevel(self, speedLevel):
            if self.speedLevel != speedLevel:
                indigo.speedcontrol.setSpeedLevel(self.id, value=speedLevel)

    ###############################################################################
    class MonitoredThermostat(object):

        #-------------------------------------------------------------------------------
        def __init__(self, thermId):
            self.id         = thermId
            self.refresh()

        #-------------------------------------------------------------------------------
        def refresh(self, therm=None):
            if not therm:
                therm = indigo.devices[self.id]
            self.name       = therm.name
            self.temp       = therm.temperatures[0]
            self.coolSet    = therm.coolSetpoint
            self.heatSet    = therm.heatSetpoint
            self.coolOn     = therm.coolIsOn
            self.heatOn     = therm.heatIsOn

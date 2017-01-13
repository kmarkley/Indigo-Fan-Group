#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# http://www.indigodomo.com

import indigo
import time

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

################################################################################
class Plugin(indigo.PluginBase):
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
    
    def __del__(self):
        indigo.PluginBase.__del__(self)

    ########################################
    # Start, Stop and Config changes
    ########################################
    def startup(self):
        self.debug = self.pluginPrefs.get('showDebugInfo',False)
        self.logger.debug("startup")
        if self.debug:
            self.logger.debug("Debug logging enabled")
        self.deviceDict = dict()
        indigo.devices.subscribeToChanges()

    ########################################
    def shutdown(self):
        self.logger.debug("shutdown")
        self.pluginPrefs['showDebugInfo'] = self.debug

    ########################################
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        self.logger.debug("closedPrefsConfigUi")
        if not userCancelled:
            self.debug = valuesDict.get("showDebugInfo",False)
            if self.debug:
                self.logger.debug("Debug logging enabled")

    ########################################
    def validatePrefsConfigUi(self, valuesDict):
        self.logger.debug("validatePrefsConfigUi")
        errorsDict = indigo.Dict()
                
        if len(errorsDict) > 0:
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)
    
    ########################################
    def runConcurrentThread(self):
        self.logger.debug("runConcurrentThread")
        try:
            while True:
                loopTime = time.time()
                for devId in self.deviceDict:
                    dev = self.deviceDict[devId]['dev']
                    if dev.deviceTypeId == 'thermAssist' and dev.onState and self.deviceDict[devId]['nextTemp']:
                        if self.deviceDict[devId]['nextTemp'] < loopTime:
                            therm = self.deviceDict[devId]['therm']
                            self.logger.debug("thermostat status request: "+therm.name)
                            indigo.device.statusRequest(therm.id, suppressLogging=(not self.debug))
                            self.deviceDict[devId]['nextTemp'] = loopTime + int(dev.pluginProps['tempFreq'])
                self.sleep(loopTime+10-time.time())
        except self.StopThread:
            pass    # Optionally catch the StopThread exception and do any needed cleanup.
    
    
    ########################################
    # Device Methods
    ########################################
    def deviceStartComm(self, dev):
        self.logger.debug("deviceStartComm: "+dev.name)
        if dev.version != self.pluginVersion:
            self.updateDeviceVersion(dev)
        if dev.id not in self.deviceDict:
            theProps = dev.pluginProps
            fanDict = {}
            for fanId in theProps.get('fans',[]):
                fanDict[int(fanId)] = indigo.devices[int(fanId)]
            thermId = int(theProps.get('thermostat',"0"))
            if thermId:
                therm = indigo.devices[thermId]
                nextTemp = time.time() + int(theProps.get('tempFreq',"300"))
            else:
                therm = None
                nextTemp = None
            self.deviceDict[dev.id] = {'dev':dev, 'fanDict':fanDict, 'therm':therm, 'nextTemp':nextTemp}
            self.updateDeviceStatus(dev)
    
    ########################################
    def deviceStopComm(self, dev):
        self.logger.debug("deviceStopComm: "+dev.name)
        if dev.id in self.deviceDict:
            del self.deviceDict[dev.id]
    
    ########################################
    def validateDeviceConfigUi(self, valuesDict, typeId, devId, runtime=False):
        self.logger.debug("validateDeviceConfigUi: " + typeId)
        errorsDict = indigo.Dict()
        
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
    
    ########################################
    def updateDeviceVersion(self, dev):
        theProps = dev.pluginProps
        # update states
        dev.stateListOrDisplayStateIdChanged()
        # check for changed props
        
        # push to server
        theProps["version"] = self.pluginVersion
        dev.replacePluginPropsOnServer(theProps)
    
    ########################################
    def updateDeviceStatus(self, dev, thermFlag=False):
        self.logger.debug("updateDeviceStatus: " + dev.name)
        theProps = dev.pluginProps
        fanDict = self.deviceDict[dev.id]['fanDict']
        
        if not fanDict:
            # this is a dummy fan
            pass
        
        # FAN GROUP FULL
        elif dev.deviceTypeId == "fanGroupFull":
            statusLogic = theProps.get('statusLogic',"avg")
            if statusLogic == "avg":
                fanIndex = 0.0
                for fanId, fan in fanDict.items():
                    fanIndex += float(fan.speedIndex)
                setSpeed = int(round(fanIndex/len(fanDict)))
            elif statusLogic == "min":
                setSpeed = min(fan.speedLevel for fanId, fan in fanDict.items())
            elif statusLogic == "max":
                setSpeed = max(fan.speedLevel for fanId, fan in fanDict.items())
            elif statusLogic == "all":
                for i in range(4):
                    if all(fan.speedIndex == i for fanId, fan in fanDict.items()):
                        setSpeed = i
                        break
                else:
                    setSpeed = 0
            dev.updateStateOnServer(key='speedIndex', value=setSpeed)
        
        # FAN GROUP SIMPLE
        elif dev.deviceTypeId == "fanGroupSimple":
            statusLogic = theProps.get('statusLogic',"any")
            onLevel = int(theProps.get('onLevel',"1"))
            if statusLogic == "any":
                onState = any(fan.speedLevel > 0 for fanId, fan in fanDict.items())
            elif statusLogic == "avg":
                fanIndex = 0.0
                for fanId, fan in fanDict.items():
                    fanIndex += float(fan.speedIndex)
                onState = int(round(fanIndex/len(fanDict))) >= onLevel
            elif statusLogic == "min":
                onState = min(fan.speedLevel for fanId, fan in fanDict.items()) >= onLevel
            elif statusLogic == "max":
                onState = max(fan.speedLevel for fanId, fan in fanDict.items()) >= onLevel
            elif statusLogic == "all":
                onState = all(fan.speedIndex == onLevel for fanId, fan in fanDict.items())
            dev.updateStateOnServer(key='onOffState', value=onState)
        
        # THERMOSTAT ASSIST
        elif dev.deviceTypeId == "thermAssist" and thermFlag:
            therm = self.deviceDict[dev.id]['therm']
            coolDelta = therm.temperatures[0] - therm.coolSetpoint
            heatDelta = therm.heatSetpoint - therm.temperatures[0]
            tempDelta = max([coolDelta,heatDelta])
            onLimit   = tempDelta > float(theProps['onThreshold'])
            offLimit  = tempDelta > float(theProps['offThreshold']) and dev.onState
            onFlag    = (therm.coolIsOn or therm.heatIsOn) and (onLimit or offLimit)
            
            onLevel   = int(theProps['onLevel'])
            allLev    = all(fan.speedIndex == onLevel for fanId, fan in fanDict.items())
            allOff    = all(fan.speedIndex == 0       for fanId, fan in fanDict.items())
            
            if onFlag and not dev.onState:
                if theProps['onOverride'] or allOff:
                    self.logger.info('"%s" on' dev.name)
                    dev.updateStateOnServer(key='onOffState', value=True)
                    self.setGroupSpeedIndex(dev, onLevel)
                    if self.deviceDict[dev.id]['nextTemp']:
                        self.deviceDict[dev.id]['nextTemp'] = time.time() + int(theProps['tempFreq'])
            elif not onFlag and dev.onState:
                self.logger.info('"%s" off' dev.name)
                dev.updateStateOnServer(key='onOffState', value=False)
                if theProps['offOverride'] or allLev:
                    self.setGroupSpeedIndex(dev, 0)
    
    ########################################
    # Device updated
    ########################################
    def deviceUpdated(self, oldDev, newDev):
        
        # device belongs to plugin
        if newDev.pluginId == self.pluginId or oldDev.pluginId == self.pluginId:
            # update local copy (will be removed/overwritten if communication is stopped/re-started)
            if newDev.id in self.deviceDict:
                self.deviceDict[newDev.id]['dev'] = newDev
            indigo.PluginBase.deviceUpdated(self, oldDev, newDev)
        
        # speedcontrol device
        elif isinstance(newDev, indigo.SpeedControlDevice) and (newDev.speedLevel != oldDev.speedLevel):
            for devId in self.deviceDict:
                for fanId, fan in self.deviceDict[devId]['fanDict'].items():
                    if newDev.id == fanId:
                        self.logger.debug("deviceUpdated: "+newDev.name)
                        # keep a copy of the updated fan
                        self.deviceDict[devId]['fanDict'][fanId] = newDev
                        # update the fan group device
                        self.updateDeviceStatus(self.deviceDict[devId]['dev'])
                        break
        
        # thermostat device
        elif isinstance(newDev, indigo.ThermostatDevice) and (newDev.states != oldDev.states):
            for devId in self.deviceDict:
                therm = self.deviceDict[devId]['therm']
                if therm and (newDev.id == therm.id):
                    self.logger.debug("deviceUpdated: "+newDev.name)
                    # keep a copy of the updated thermostat
                    self.deviceDict[devId]['therm'] = newDev
                    # update the fan group device
                    self.updateDeviceStatus(self.deviceDict[devId]['dev'], True)
    
    ########################################
    # Action Methods
    ########################################
    def actionControlSpeedControl(self, action, dev):
        self.logger.debug("actionControlSpeedControl: "+dev.name)
        # TURN ON
        if action.speedControlAction == indigo.kSpeedControlAction.TurnOn:
            self.logger.info('"%s" on' % dev.name)
            self.setGroupSpeedIndex(dev, 1)
        # TURN OFF
        elif action.speedControlAction == indigo.kSpeedControlAction.TurnOff:
            self.logger.info('"%s" off' % dev.name)
            self.setGroupSpeedIndex(dev, 0)
        # TOGGLE
        elif action.speedControlAction == indigo.kSpeedControlAction.Toggle:
            self.logger.info('"%s" %s' % (dev.name, ['on','off'][dev.onState]))
            self.setGroupSpeedIndex(dev, [1,0][dev.onState])
        # SET SPEED INDEX
        elif action.speedControlAction == indigo.kSpeedControlAction.SetSpeedIndex:
            self.logger.info('"%s" set motor speed to %s' % (dev.name, kSpeedIndex[action.actionValue]))
            self.setGroupSpeedIndex(dev, action.actionValue)
        # SET SPEED LEVEL
        elif action.speedControlAction == indigo.kSpeedControlAction.SetSpeedLevel:
            self.logger.info('"%s" set motor speed to %s' % (dev.name, action.actionValue))
            self.setGroupSpeedLevel(dev, action.actionValue)
        # INCREASE SPEED INDEX
        elif action.speedControlAction == indigo.kSpeedControlAction.IncreaseSpeedIndex:
            newSpeedIndex = dev.speedIndex + action.actionValue
            if newSpeedIndex > 3:
                newSpeedIndex = 3
            self.logger.info('"%s" set motor speed to %s' % (dev.name, kSpeedIndex[newSpeedIndex]))
            self.setGroupSpeedIndex(dev, newSpeedIndex)
        # DECREASE SPEED INDEX
        elif action.speedControlAction == indigo.kSpeedControlAction.DecreaseSpeedIndex:
            newSpeedIndex = dev.speedIndex - action.actionValue
            if newSpeedIndex < 0:
                newSpeedIndex = 0
            self.logger.info('"%s" set motor speed to %s' % (dev.name, kSpeedIndex[newSpeedIndex]))
            self.setGroupSpeedIndex(dev, newSpeedIndex)
        # STATUS REQUEST
        elif action.speedControlAction == indigo.kUniversalAction.RequestStatus:
            self.logger.info('"%s" status update' % dev.name)
            self.updateDeviceStatus(dev)
        # UNKNOWN
        else:
            self.logger.debug('"%s" %s request ignored' % (dev.name, unicode(action.speedControlAction)))
            
    
    ########################################
    def actionControlDimmerRelay(self, action, dev):
        self.logger.debug("actionControlDimmerRelay: "+dev.name)
        # TURN ON
        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            self.logger.info('"%s" on' % dev.name)
            self.setGroupSpeedIndex(dev, int(dev.pluginProps.get('onLevel',1)))
        # TURN OFF
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            self.logger.info('"%s" off' % dev.name)
            self.setGroupSpeedIndex(dev, 0)
        # TOGGLE
        elif action.deviceAction == indigo.kDeviceAction.Toggle:
            self.logger.info('"%s" %s' % (dev.name, ['on','off'][dev.onState]))
            self.setGroupSpeedIndex(dev, [int(dev.pluginProps.get('onLevel',1)),0][dev.onState])
        # STATUS REQUEST
        elif action.deviceAction == indigo.kUniversalAction.RequestStatus:
            self.logger.info('"%s" status update' % dev.name)
            self.updateDeviceStatus(dev)
        # UNKNOWN
        else:
            self.logger.debug('"%s" %s request ignored' % (dev.name, unicode(action.deviceAction)))
    
    ########################################
    def actionControlSensor(self, action, dev):
        self.logger.debug("actionControlSensor: "+dev.name)
        # STATUS REQUEST
        if action.sensorAction == indigo.kUniversalAction.RequestStatus:
            self.logger.info('"%s" status request' % dev.name)
            self.updateDeviceStatus(dev)
        # UNKNOWN
        else:
            self.logger.debug('"%s" %s request ignored' % (dev.name, unicode(action.sensorAction)))
    
    ########################################
    # Menu Methods
    ########################################
    def toggleDebug(self):
        if self.debug:
            self.logger.debug("Debug logging disabled")
            self.debug = False
        else:
            self.debug = True
            self.logger.debug("Debug logging enabled")
        
    ########################################
    # Menu Callbacks
    ########################################
    def getSpeedControlDeviceList(self, filter="", valuesDict=None, typeId="", targetId=0):
        devList = []
        excludeList  = [dev.id for dev in indigo.devices.iter(filter='self')]
        for dev in indigo.devices.iter(filter='indigo.speedcontrol'):
            if not dev.id in excludeList:
                devList.append((dev.id, dev.name))
        return devList        
        
    ########################################
    # Utilities
    ########################################
    def setGroupSpeedIndex(self, dev, speedIndex):
        fanDict = self.deviceDict[dev.id]['fanDict']
        if fanDict:
            for fanId, fan in fanDict.items():
                if fan.speedIndex != speedIndex:
                    indigo.speedcontrol.setSpeedIndex(fanId, value=speedIndex)
        else: # this is a dummy fan
            dev.updateStateOnServer(key='speedIndex', value=speedIndex)
    
    ########################################
    def setGroupSpeedLevel(self, dev, speedLevel):
        fanDict = self.deviceDict[dev.id]['fanDict']
        if fanDict:
            for fanId, fan in fanDict.items():
                if fan.speedLevel != speedLevel:
                    indigo.speedcontrol.setSpeedLevel(fanId, value=speedLevel)
        else: # this is a dummy fan
            dev.updateStateOnServer(key='speedLevel', value=speedLevel)
